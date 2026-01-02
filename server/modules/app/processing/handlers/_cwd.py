import logging
from server.modules.app.processing import Command
from server.modules.discovery import NodeType
from server.modules.app.routing import ClientSession
from server.modules.comm import Message, MessageType

logger = logging.getLogger("dftp.processing.handlers.cwd")

def handle_cwd(cmd: Command, data: dict = None, processing_node = None) -> tuple[int, str, dict]:
    """Maneja el comando CWD <directory>."""

    if not cmd.require_args(1):
        return 501, "Syntax error in parameters. Usage: CWD <directory>", None

    if not data or not processing_node:
        return 500, "Internal server error.", None

    session = ClientSession.from_json(data)

    if not session.is_authenticated():
        return 530, "Not logged in.", None

    new_path = cmd.get_arg(0)
    data_nodes = processing_node.query_by_role(NodeType.DATA)

    if not data_nodes:
        logger.warning("No DataNodes available for CWD command")
        return 451, "Requested action aborted. File system unavailable.", None

    response = None

    for data_node in data_nodes:
        try:
            msg = Message(MessageType.DATA_CWD, processing_node.ip, data_node["ip"], payload={"user": session.get_username(), "current_path": session.get_cwd(), "new_path": new_path})

            response = processing_node.send_message(data_node["ip"], 9000, msg, await_response=True)

            if response:
                break

        except Exception as e:
            logger.warning("Failed to contact DataNode (%s): %s", data_node["ip"], e)

    if not response:
        return 451, "Requested action aborted. File system unavailable.", None

    if response.metadata.get("status") != "OK":
        return 550, response.metadata.get("message", "Failed to change directory."), None

    new_cwd = response.payload.get("cwd")

    if not new_cwd:
        return 550, "Failed to change directory.", None

    session.set_cwd(new_cwd)
    return 250, f'Directory successfully changed to "{new_cwd}".', session.to_json()
