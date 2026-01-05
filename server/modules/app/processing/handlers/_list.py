import logging
from server.modules.app.processing import Command
from server.modules.discovery import NodeType
from server.modules.app.routing import ClientSession
from server.modules.comm import Message, MessageType

logger = logging.getLogger("dftp.processing.handlers.list")

def handle_list(cmd: Command, data: dict = None, processing_node=None) -> tuple[int, str, dict]:
    """LIST: Lista archivos y directorios. Solo acepta 0 o 1 argumento (path)."""

    if not data or not processing_node:
        return 500, "Internal server error.", None

    session = ClientSession.from_json(data)

    if not session.is_authenticated():
        return 530, "Not logged in.", None

    if cmd.arg_count() > 1:
        return 501, "Syntax error in parameters. Usage: LIST [<path>]", None
    path = cmd.get_arg(0) if cmd.arg_count() == 1 else "."

    pasv_info = session.get_pasv_mode_info()

    if not pasv_info:
        return 425, "Use PASV first.", None
    
    primary_ip, _ = pasv_info

    try:
        msg = Message(type=MessageType.DATA_LIST, src=processing_node.ip, dst=primary_ip, payload={"user": session.get_username(), "cwd": session.get_cwd(), "path": path, "session_id": session.get_session_id(), "detailed": True})
        response = processing_node.send_message(primary_ip, 9000, msg, await_response=True, timeout=300)

    except Exception as e:
        logger.exception("Failed to contact DataNode (%s) for LIST: %s", primary_ip, e)
        return 451, "Requested action aborted. File system unavailable.", None

    session.clear_pasv()

    if not response:
        return 451, "Requested action aborted. File system unavailable.", None

    if response.metadata.get("status") != "OK":
        error_msg = response.metadata.get("message", "Failed to list directory.")
        return 550, error_msg, None

    return 212, "Directory listing successful.", None
