import logging
from server.modules.app.processing import Command
from server.modules.discovery import NodeType
from server.modules.app.routing import ClientSession
from server.modules.comm import Message, MessageType

logger = logging.getLogger("dftp.processing.handlers.stat")

def handle_stat(cmd: Command, data: dict = None, processing_node=None) -> tuple[int, str, dict]:
    """
    STAT: Status.
    - Sin argumentos: devuelve info de la sesión actual.
    - Con un argumento <path>: consulta a un DataNode para obtener información del path.
    - Más de un argumento: error de sintaxis.
    """

    if not data:
        return 530, "Not logged in.", None

    session = ClientSession.from_json(data)

    if not session.is_authenticated():
        return 530, "Not logged in.", None

    # 0 argumentos → info de sesión
    if cmd.require_args(0):
        return 211, f"Session info: {str(session)}", session.to_json()

    # 1 argumento → info de path
    elif cmd.require_args(1):
        path = cmd.get_arg(0)
        data_nodes = processing_node.query_by_role(NodeType.DATA)

        if not data_nodes:
            logger.warning("No DataNodes available for STAT command")
            return 451, "Requested action aborted. File system unavailable.", session.to_json()

        response = None
        
        for data_node in data_nodes:
            try:
                msg = Message(MessageType.DATA_STAT, src=processing_node.ip, dst=data_node["ip"], payload={"user": session.get_username(), "cwd": session.get_cwd(), "path": path})
                
                response = processing_node.send_message(data_node["ip"], 9000, msg, await_response=True)
                
                if response:
                    break

            except Exception as e:
                logger.warning("Failed to contact DataNode (%s) during STAT: %s", data_node["ip"], e)
                continue

        if not response:
            return 451, "Requested action aborted. File system unavailable.", session.to_json()

        if response.metadata.get("status") != "OK":
            error_msg = response.metadata.get("message", "Failed to stat path.")
            return 550, error_msg, session.to_json()

        stat_info = response.payload.get("stat")
        if not stat_info:
            return 550, "Failed to retrieve stat info.", session.to_json()

        return 211, f"STAT for '{path}': {stat_info}", session.to_json()

    # >1 argumento → error de sintaxis
    else:
        return 501, "Syntax error in parameters.", None
