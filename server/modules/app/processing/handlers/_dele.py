import logging
from server.modules.app.processing import Command
from server.modules.discovery import NodeType
from server.modules.app.routing import ClientSession
from server.modules.comm import Message, MessageType

logger = logging.getLogger("dftp.processing.handlers.dele")

def handle_dele(cmd: Command, data: dict = None, processing_node=None) -> tuple[int, str, dict]:
    """Maneja el comando DELE <file> para eliminar un archivo."""

    if not cmd.require_args(1):
        return 501, "Syntax error in parameters. Usage: DELE <file>", None

    if not data or not processing_node:
        return 500, "Internal server error.", None

    session = ClientSession.from_json(data)

    if not session.is_authenticated():
        return 530, "Not logged in.", None

    target_path = cmd.get_arg(0)
    data_nodes = processing_node.query_by_role(NodeType.DATA)

    if not data_nodes:
        logger.warning("No DataNodes available for DELE command")
        return 451, "Requested action aborted. File system unavailable.", None

    response = None

    for data_node in data_nodes:
        try:
            msg = Message(MessageType.DATA_REMOVE, processing_node.ip, data_node["ip"], payload={"user": session.get_username(), "cwd": session.get_cwd(), "path": target_path, "type": "file"})

            response = processing_node.send_message(data_node["ip"], 9000, msg, await_response=True)

            if response:
                break

        except Exception as e:
            logger.warning("Failed to contact DataNode (%s): %s", data_node["ip"], e)
            continue

    if not response:
        return 451, "Requested action aborted. File system unavailable.", None

    if response.metadata.get("status") != "OK":
        return 550, response.metadata.get("message", "Failed to delete file."), None

    return 250, f"File '{target_path}' deleted successfully.", None
