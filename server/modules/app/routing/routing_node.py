import socket
import threading
import logging
import uuid
from typing import List
import time

from server.modules.consistency import GossipNode
from server.modules.discovery import NodeType
from server.modules.comm import Message, MessageType
from server.modules.app.routing.client_session.client_session import ClientSession
from server.modules.app.routing.client_session.session_table import SessionTable

INTERNAL_PORT = 9000

logger = logging.getLogger("dftp.routing.routing_node")

class NoProcessingNodeException(Exception):
    """No hay processing nodes disponibles para despachar comandos FTP."""
    pass

class RoutingNode(GossipNode):
    """
    RoutingNode:

    - Escucha conexiones FTP entrantes (canal de control)
    - Por cada cliente aceptado lanza un handler en un hilo separado
    - Mantiene sesiones de clientes en un diccionario _sessions
    """

    def __init__(self, node_name: str, ip: str, ftp_port: int = 21, internal_port: int = 9000, discovery_timeout: float = 0.8, heartbeat_interval: int = 2):
        # Inicializar GossipNode para permitir replicación de estado entre routing nodes   
        self._session_table = SessionTable()
        self.ftp_port = ftp_port
        
        super().__init__(node_name=node_name, ip=ip, port=internal_port, discovery_timeout=discovery_timeout, heartbeat_interval=heartbeat_interval, node_role=NodeType.ROUTING)

        self.register_handler(MessageType.DATA_READY, self._handle_data_ready)
        self._start_ftp_listener()


    def _start_ftp_listener(self) -> None :
        """Abre un socket que se mantendrá a la espera de nuevas conexiones por partes de clientes"""

        self.ftp_server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ftp_server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ftp_server_sock.bind((self.ip, self.ftp_port))
        self.ftp_server_sock.listen(50)

        logger.info("[RoutingNode %s] FTP escuchando en %s:%s", self.node_name, self.ip, self.ftp_port)

        # Hilo que espera nuevas conexiones
        threading.Thread(target=self._wait_for_connections, daemon=True).start()


    def _wait_for_connections(self) -> None :
        """
        Bucle que acepta nuevas conexiones FTP.
        Cada cliente se maneja en un hilo independiente.
        """
        logger.info("[%s] Iniciando espera de conexiones FTP", self.node_name)

        while True:
            try:
                client_sock, client_addr = self.ftp_server_sock.accept()
                logger.info("[%s] Cliente FTP conectado desde %s", self.node_name, client_addr)

                # Encargarse de cada cliente en un hilo independiente
                threading.Thread(target=self._handle_client, args=(client_sock, client_addr), daemon=True,).start()

            except Exception:
                logger.exception("[%s] Error aceptando conexión FTP", self.node_name)


    def _handle_client(self, client_sock, client_addr) -> None:

        session_id = str(uuid.uuid4())
        session = ClientSession(session_id=session_id, client_ip=client_addr[0], control_socket=client_sock)

        # Registrar la sesión en la tabla
        self._session_table.add(session)

        # Notificar peers (gossip) del nuevo estado de sesión
        try:
            self.notify_local_change({"op": "add", "session": session.to_json()})
        except Exception:
            logger.debug("[%s] notify_local_change failed on add", self.node_name)

        try:
            session.send_response(220, "Distributed FTP Server Ready")
            logger.info("[%s] Sesión creada para %s: %s", self.node_name, client_addr, session)

            for line in session.recv_lines():
                if not line:
                    continue

                try:
                    close_session = self._dispatch_ftp_command(session, line)
                    if close_session:
                        break

                except NoProcessingNodeException:
                    session.send_response(421, "Service not available")
                    break

                except Exception:
                    logger.exception("[%s][%s] Error dispatching command", self.node_name, session_id)
                    session.send_response(451, "Requested action aborted. Local error in processing")

        except Exception:
            logger.exception("[%s] Error en la sesión de %s", self.node_name, client_addr)

        finally:
            try:
                client_sock.close()

            except Exception:
                pass

            # Eliminar de la tabla de sesiones
            self._session_table.remove_by_id(session_id)
            try:
                self.notify_local_change({"op": "delete", "session_id": session_id})
            except Exception:
                logger.debug("[%s] notify_local_change failed on delete", self.node_name)

    def _dispatch_ftp_command(self, session: ClientSession, line: str) -> bool:
        """
        Envía un comando FTP a un processing node.
        Retorna True si la sesión debe cerrarse. """

        processing_nodes = self.get_processing_nodes()
        last_error = None

        for processing_node in processing_nodes:
            try:
                processing_node_ip = processing_node["ip"]
                message = self._build_process_command_msg(session, line, processing_node_ip)
                response = self.send_message(processing_node_ip, 9000, message, timeout=300)
                return self._handle_processing_response(response, session)

            except Exception as e:
                logger.warning("[%s][%s] Processing node %s failed: %s", self.node_name, session.session_id, processing_node_ip, e)
                last_error = e
                continue

        # Si llegamos aquí, ninguno respondió
        raise NoProcessingNodeException("All processing nodes failed") from last_error
    
    def _handle_data_ready(self, message: "Message") -> Message:
        """
        Handler para mensajes de tipo DATA_READY.
        Envía un 150 Data connection ready al cliente y responde al DataNode.
        Payload esperado:
            - session_id: str
        """
        payload = message.payload or {}
        session_id = payload.get("session_id")

        if not session_id:
            logger.warning("[%s] DATA_READY recibido sin session_id", self.node_name)
            return Message(MessageType.DATA_READY_ACK, self.ip, message.header.get("src"), payload={"success": False})

        session = self._session_table.get_by_id(session_id)
            
        if not session:
            logger.warning("[%s] No se encontró sesión para session_id %s", self.node_name, session_id)
            return Message(MessageType.DATA_READY_ACK, self.ip, message.header.get("src"), payload={"success": False})

        try:
            session.send_response(150, "Data connection ready")
            logger.info("[%s] Enviado 150 al cliente para session %s", self.node_name, session_id)

        except Exception:
            logger.exception("[%s] Error enviando 150 al cliente para session %s", self.node_name, session_id)
            return Message(MessageType.DATA_READY_ACK, self.ip, message.header.get("src"), payload={"success": False})

        # Respuesta al DataNode para que continúe la transferencia
        return Message(MessageType.DATA_READY_ACK, self.ip, message.header.get("src"), payload={"success": True})


    def get_session_by_id(self, session_id: str) -> ClientSession | None:
        """Retorna la sesión correspondiente a session_id, o None si no existe"""
        return self._session_table.get_by_id(session_id)

    def get_processing_nodes(self) -> list:
        """Obtiene la lista de processing nodes disponibles"""
        nodes = self.query_by_role(NodeType.PROCESSING)
        if not nodes:
            raise NoProcessingNodeException("No processing nodes available")
        return nodes

    def _build_process_command_msg(self, session : ClientSession, line : str, dst : str) -> Message :
        """Construye un mensaje de tipo PROCESS_FTP_COMMAND para ser enviado a un processing node """
        msg = Message(MessageType.PROCESS_FTP_COMMAND, self.ip, dst, payload={"line" : line, "session" : session.to_json()})
        return msg
    
    def _handle_processing_response(self, response: Message, session: ClientSession) -> bool:
        """
        Procesa la respuesta del processing node.
        Retorna True si se debe cerrar la sesión. """
        logger.info("Received: %s", response)

        if not response:
            return

        code = response.payload.get("code", 500)
        ftp_msg = response.payload.get("message", "Unknown error")
        new_session = response.payload.get("session")

        if new_session is not None:
            changed = session.update_session(new_session)
            if changed:
                try:
                    self.notify_local_change({"op": "add", "session": session.to_json()})
                except Exception:
                    logger.debug("[%s] notify_local_change failed on update", self.node_name)

        session.send_response(code, ftp_msg)

        return code == 221


    # ----------------- Gossip / Session replication -----------------
    def _export_sessions(self) -> list:
        """Exporta todas las sesiones como lista de dicts."""
        try:
            return [s.to_json() for s in self._session_table.get_all_sessions()]
        except Exception:
            logger.exception("[%s] Error exporting sessions", self.node_name)
            return []

    def _import_sessions(self, sessions: list[dict]):
        """Importa (merge) una lista de sesiones replicadas."""
        if not sessions:
            return
        try:
            for sdata in sessions:
                try:
                    s = ClientSession.from_json(sdata)
                    self._session_table.add(s) 

                except Exception:
                    logger.debug("[%s] Failed importing session %s", self.node_name, sdata.get("session_id"))

        except Exception:
            logger.exception("[%s] Error importing sessions", self.node_name)

    def _on_gossip_update(self, update: dict):
        """Aplica cambios recibidos via gossip (add/delete)."""
        logger.info("[%s] Received gossip update: %s", self.node_name, update)

        op = update.get("op")
        
        if not op:
            return

        if op == "add":
            session_data = update.get("session")
            if not session_data:
                return
            try:
                s = ClientSession.from_json(session_data)
                self._session_table.add(s)
            except Exception:
                logger.exception("[%s] Error applying gossip add", self.node_name)

        elif op == "delete":
            sid = update.get("session_id")
            if not sid:
                return
            try:
                self._session_table.remove_by_id(sid)
            except Exception:
                logger.exception("[%s] Error applying gossip delete", self.node_name)
        
        logger.info("[%s] Applied gossip update: %s", self.node_name, op)
        logger.info("[%s] Current sessions: %s", self.node_name, self._session_table)

    def _merge_state(self, peer_ip: str):
        """Inicia merge bidireccional con peer_ip."""

        data = {"sessions": self._export_sessions()}
        
        msg = Message(MessageType.MERGE_STATE, self.ip, peer_ip, payload=data)
        
        try:
            logger.info("[%s] Enviando MERGE_STATE a %s", self.node_name, peer_ip)
            
            response = self.send_message(peer_ip, 9000, msg, await_response=True, timeout=30)

            logger.info("[%s] Recibiendo respuesta de MERGE_STATE de %s", self.node_name, peer_ip)
            
            if response and response.payload.get("sessions"):
                self._import_sessions(response.payload.get("sessions"))
        
        except Exception:
            logger.exception("[%s] Error durante MERGE_STATE con %s", self.node_name, peer_ip)

        logger.info("[%s] Merge de estado completado con %s", self.node_name, peer_ip)

    def _handle_merge_state(self, message: Message) -> Message:
        try:
            logger.info("[%s] Recibiendo MERGE_STATE de %s", self.node_name, message.header.get("src"))
            payload = message.payload or {}
            sessions = payload.get("sessions", [])
            self._import_sessions(sessions)

            # Responder con nuestro estado
            data = {"sessions": self._export_sessions()}
            logger.info("[%s] Enviando MERGE_STATE_ACK a %s", self.node_name, message.header.get("src"))

            logger.info("[%s] Current sessions after MERGE_STATE: %s", self.node_name, self._session_table)
            return Message(MessageType.MERGE_STATE_ACK, self.ip, message.header.get("src"), payload=data)
        
        except Exception:
            logger.exception("[%s] Error en _handle_merge_state", self.node_name)
            return Message(MessageType.MERGE_STATE_ACK, self.ip, message.header.get("src"), payload={})
            

    def send_state(self, peer_ip: str):
        """Envía el estado propio a otro nodo sin esperar respuesta."""

        data = {"sessions": self._export_sessions()}
        
        msg = Message(MessageType.SEND_STATE, self.ip, peer_ip, payload=data)
        try:
            logger.info("[%s] Enviando SEND_STATE a %s", self.node_name, peer_ip)
            self.send_message(peer_ip, 9000, msg, await_response=False)

        except Exception:
            logger.exception("[%s] Error enviando SEND_STATE a %s", self.node_name, peer_ip)

    def _handle_send_state(self, message: Message):
        try:
            payload = message.payload or {}
            sessions = payload.get("sessions", [])
            self._import_sessions(sessions)
            logger.info("[%s] Estado actualizado desde SEND_STATE de %s", self.node_name, message.header.get("src"))
        
        except Exception:
            logger.exception("[%s] Error en _handle_send_state", self.node_name)

        logger.info("[%s] Current sessions after SEND_STATE: %s", self.node_name, self._session_table)


