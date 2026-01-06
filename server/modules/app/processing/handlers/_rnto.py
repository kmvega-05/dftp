import logging
from server.modules.app.processing import Command
from server.modules.discovery import NodeType
from server.modules.app.routing import ClientSession
from server.modules.comm import Message, MessageType

logger = logging.getLogger("dftp.processing.handlers.rnto")

def handle_rnto(cmd: Command, data: dict = None, processing_node=None) -> tuple[int, str, dict]:
    """Maneja el comando RNTO <new_path> para completar un renombrado."""

    if not cmd.require_args(1):
        return 501, "Syntax error in parameters. Usage: RNTO <new_path>", None

    if not data or not processing_node:
        return 500, "Internal server error.", None

    session = ClientSession.from_json(data)

    if not session.is_authenticated():
        return 530, "Not logged in.", None

    old_path = session.get_rename_from()
    new_path = cmd.get_arg(0)

    if not old_path or old_path == "":
        return 503, "Bad sequence of commands. Use RNFR first.", None

    data_nodes = processing_node.query_by_role(NodeType.DATA)
    if not data_nodes:
        return 451, "Requested action aborted. File system unavailable.", None

    response = None

    for data_node in data_nodes:
        try:
            msg = Message(MessageType.DATA_RENAME, processing_node.ip, data_node["ip"], payload={"user": session.get_username(), "cwd": session.get_cwd(), "old_path": old_path, "new_path": new_path})

            response = processing_node.send_message(data_node["ip"], 9000, msg, await_response=True)
            if response:
                break

        except Exception as e:
            logger.warning("Failed to contact DataNode (%s): %s", data_node["ip"], e)
            continue

    session.clear_rename_from()

    if not response:
        return 451, "Requested action aborted. File system unavailable.", session.to_json()

    if response.metadata.get("status") != "OK":
        return 550, response.metadata.get("message", "Rename failed."), session.to_json()

    return 250, f"Renamed '{old_path}' to '{new_path}' successfully.", session.to_json()
