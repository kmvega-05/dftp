import logging
from server.modules.app.processing import Command
from server.modules.discovery import NodeType
from server.modules.app.routing import ClientSession
from server.modules.comm import Message, MessageType

logger = logging.getLogger("dftp.processing.handlers.retr")

def handle_retr(cmd: Command, data: dict = None, processing_node=None) -> tuple[int, str, dict]:
    """ Maneja el comando RETR <filename> para descargar un archivo del servidor. """

    if not cmd.require_args(1):
        return 501, "Syntax error in parameters. Usage: RETR <filename>", None

    if not data or not processing_node:
        return 500, "Internal server error.", None

    session = ClientSession.from_json(data)
    filename = cmd.get_arg(0)

    if not session.is_authenticated():
        return 530, "Not logged in.", None

    data_nodes = processing_node.query_by_role(NodeType.DATA)
    if not data_nodes:
        logger.warning("No DataNodes available for RETR command")
        return 451, "Requested action aborted. File system unavailable.", None

    response = None

    for data_node in data_nodes:
        try:
            msg = Message(type=MessageType.DATA_RETR_FILE, src=processing_node.ip, dst=data_node["ip"], payload={"user": session.get_username(), "cwd": session.get_cwd(), "path": filename, "session_id": session.get_session_id(), "chunk_size": 65536})

            # Envía el mensaje al DataNode y espera a que termine la transferencia
            response = processing_node.send_message(data_node["ip"], 9000, msg, await_response=True, timeout=300)

            if response:
                break

        except Exception as e:
            logger.warning("Failed to contact DataNode (%s) for RETR: %s", data_node["ip"], e)
            continue

    if not response:
        return 451, "Requested action aborted. File system unavailable.", session.to_json()

    if response.metadata.get("status") != "OK":
        error_msg = response.metadata.get("message", "Failed to retrieve file.")
        return 550, error_msg, session.to_json()

    return 212, f"File '{filename}' transferred successfully.", session.to_json()
