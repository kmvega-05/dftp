import socket
import threading
import logging
import uuid

from server.modules.discovery import LocationNode, NodeType
from server.modules.comm import Message, MessageType
from server.modules.app.routing.client_session.client_session import ClientSession

INTERNAL_PORT = 9000

logger = logging.getLogger("dftp.routing.routing_node")

class NoProcessingNodeException(Exception):
    """No hay processing nodes disponibles para despachar comandos FTP."""
    pass

class RoutingNode(LocationNode):
    """
    RoutingNode:

    - Escucha conexiones FTP entrantes (canal de control)
    - Por cada cliente aceptado lanza un handler en un hilo separado
    - Mantiene sesiones de clientes en un diccionario _sessions
    """

    def __init__(self, node_name: str, ip: str, ftp_port: int = 21, internal_port: int = 9000, discovery_timeout: float = 0.8, heartbeat_interval: int = 2):
        super().__init__(node_name=node_name, ip=ip, port=internal_port, node_role=NodeType.ROUTING, discovery_timeout=discovery_timeout, heartbeat_interval=heartbeat_interval)

        self.ftp_port = ftp_port
        self._sessions: dict[str, ClientSession] = {}  # Diccionario de session_id -> ClientSession
        self._sessions_lock = threading.Lock()

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
        
        with self._sessions_lock:
            self._sessions[session_id] = session 

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

            with self._sessions_lock:
                self._sessions.pop(session_id, None)

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

        with self._sessions_lock:
            session = self._sessions.get(session_id)
            
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
        with self._sessions_lock:
            return self._sessions.get(session_id)

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
            session.update_session(new_session)

        session.send_response(code, ftp_msg)

        return code == 221


