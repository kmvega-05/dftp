import logging
from server.modules.app.processing import Command
from server.modules.discovery import NodeType
from server.modules.app.routing import ClientSession
from server.modules.comm import Message, MessageType

logger = logging.getLogger("dftp.processing.handlers.nlst")

def handle_nlst(cmd: Command, data: dict = None, processing_node=None) -> tuple[int, str, dict]:
    """NLST: Lista archivos y directorios(de forma sencilla). Solo acepta 0 o 1 argumento (path)."""

    if not data or not processing_node:
        return 500, "Internal server error.", None

    session = ClientSession.from_json(data)

    if not session.is_authenticated():
        return 530, "Not logged in.", None

    # NLST solo acepta 0 o 1 argumento
    if cmd.arg_count() > 1:
        return 501, "Syntax error in parameters. Usage: NLST [<path>]", None
    path = cmd.get_arg(0) if cmd.arg_count() == 1 else "."

    # Resolver DataNode
    data_nodes = processing_node.query_by_role(NodeType.DATA)
    if not data_nodes:
        return 451, "Requested action aborted. File system unavailable.", None

    response = None
    for data_node in data_nodes:
        try:
            msg = Message(type=MessageType.DATA_LIST, src=processing_node.ip, dst=data_node["ip"], payload={"user": session.get_username(), "cwd": session.get_cwd(), "path": path, "session_id": session.get_session_id(), "detailed": False})
            response = processing_node.send_message(data_node["ip"], 9000, msg, await_response=True)
            if response:
                break

        except Exception as e:
            logger.warning("Failed to contact DataNode (%s): %s", data_node["ip"], e)
            continue
    
    session.clear_pasv()
    
    if not response:
        return 451, "Requested action aborted. File system unavailable.", session.to_json()

    if response.metadata.get("status") != "OK":
        error_msg = response.metadata.get("message", "Failed to list directory.")
        return 550, error_msg, session.to_json()

    # Todo salió bien, se recibió 212 del DataNode
    return 212, "Directory listing successful.", session.to_json()
