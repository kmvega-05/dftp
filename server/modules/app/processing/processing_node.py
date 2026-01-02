import logging
import threading

from server.modules.discovery import LocationNode, NodeType
from server.modules.app.processing.command import Command
from server.modules.app.processing.handlers_dispatch import FTP_COMMAND_HANDLERS
from server.modules.comm import Message, MessageType

logger = logging.getLogger("dftp.processing.processing_node")


class ProcessingNode(LocationNode):

    def __init__(self, node_name: str, ip: str, internal_port: int = 9000, discovery_timeout: float = 0.8, heartbeat_interval: int = 2):
        super().__init__(node_name=node_name, ip=ip, port=internal_port, node_role=NodeType.PROCESSING, discovery_timeout=discovery_timeout, heartbeat_interval=heartbeat_interval)

        self._active_sessions: dict[str, str] = {}
        self._sessions_lock = threading.Lock()

        # Registrar handlers
        self.register_handler(MessageType.PROCESS_FTP_COMMAND, self._handle_process_ftp_command)
        self.register_handler(MessageType.DATA_READY, self._handle_data_ready)

        logger.info("[%s] ProcessingNode iniciado en %s:%s", node_name, ip, internal_port)

    
    def _handle_process_ftp_command(self, message: Message) -> Message:
        """
        Maneja PROCESS_FTP_COMMAND.
        """
        payload = message.payload or {}

        dst = message.header.get("src")
        raw_line = payload.get("line")
        session_data = payload.get("session")
        session_id = session_data.get("session_id")

        with self._sessions_lock:
            logger.info("Active session: %s, %s", session_id, dst)
            self._active_sessions[session_id] = dst

        logger.info(f"[{self.node_name}] Received PROCESS_FTP_COMMAND request from {dst} : {raw_line}")

        if raw_line is None:
            logger.warning("[%s] Payload inválido: %s", self.node_name, payload)
            return self._build_response(dst, 500, "Invalid Command.", None)

        # Parseo del comando FTP
        cmd = Command(raw_line)

        if cmd.is_empty():
            logger.debug("[%s] Comando vacío recibido", self.node_name)
            return self._build_response(dst, 500, "Empty Command.", None)

        logger.debug("[%s] Parsed command: name=%s args=%s", self.node_name, cmd.get_name(), cmd.get_args())

        handler = FTP_COMMAND_HANDLERS.get(cmd.get_name())

        if not handler:
            return self._build_response(dst, 502, "Command not implemented.", None)
        
        try :
            code, message, session_data = handler(cmd, session_data, self)
        
        except Exception as e:
            logger.warning(f"Error manejando comando: {str(e)}")
            return self._build_response(dst, 451, "Internal Server Error", None)

        return self._build_response(dst, code, message, session_data)
    
    def _handle_data_ready(self, message: Message) -> Message:

        try:
            logger.info("Received DATA_READY from %s", message.header.get("src"))
            session_id = message.payload.get("session_id")

            with self._sessions_lock:
                routing_ip = self._active_sessions.get(session_id)

            logger.info("Resolved routing node ip: %s", routing_ip)
            if not routing_ip:
                logger.warning("No routing node for session %s", session_id)
                return Message(MessageType.DATA_READY_ACK, self.ip, message.header.get("src"), payload={"success": False})

            msg = Message(MessageType.DATA_READY, self.ip, routing_ip, payload={"session_id": session_id})

            logger.info("Sending DATA READY to Routing node.")
            response = self.send_message(routing_ip, 9000, msg, await_response=True)
            logger.info("RECEIVED: %s" , response)

            if not response:
                logger.warning("Routing node %s did not ACK DATA_READY", routing_ip)
                return Message(MessageType.DATA_READY_ACK, self.ip, message.header.get("src"), payload={"success": False})

            return Message(MessageType.DATA_READY_ACK, self.ip, message.header.get("src"), payload={"success": response.payload.get("success")})

        except Exception as e:
            logger.exception("Failed forwarding DATA_READY for session %s: %s", session_id, e)
            return Message(MessageType.DATA_READY_ACK, self.ip, message.header.get("src"), payload={"success": False})

    def _build_response(self, dst : str, code : int, message : str, session_data : dict ) :
        logger.info(f"[{self.node_name}] Sending response to {dst} : ({code}, {message})")
        return Message(MessageType.PROCESS_FTP_COMMAND_ACK, self.ip, dst, payload = {"code": code, "message": message, "session" : session_data})

