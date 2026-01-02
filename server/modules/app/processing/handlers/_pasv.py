import logging
from server.modules.app.processing import Command
from server.modules.discovery import NodeType
from server.modules.app.routing import ClientSession
from server.modules.comm import Message, MessageType

logger = logging.getLogger("dftp.processing.handlers.pasv")

def handle_pasv(cmd: Command, data: dict = None, processing_node=None) -> tuple[int, str, dict]:
    """Maneja el comando PASV - pasar al modo pasivo y obtener IP/puerto para transferencia de datos."""

    if not cmd.require_args(0):
        return 501, "Syntax error in parameters. Usage: PASV", None

    if not data or not processing_node:
        return 500, "Internal server error.", None

    session = ClientSession.from_json(data)

    if not session.is_authenticated():
        return 530, "Not logged in.", None

    data_nodes = processing_node.query_by_role(NodeType.DATA)
    if not data_nodes:
        logger.warning("No DataNodes available for PASV command")
        return 451, "Requested action aborted. File system unavailable.", None

    response = None
    session_id = session.get_session_id()

    for data_node in data_nodes:
        try:
            msg = Message(type=MessageType.DATA_OPEN_PASV, src=processing_node.ip, dst=data_node["ip"], payload={"session_id": session_id})
            response = processing_node.send_message(data_node["ip"], 9000, msg, await_response=True)

            if response:
                break

        except Exception as e:
            logger.warning("Failed to contact DataNode (%s): %s", data_node["ip"], e)
            continue

    if not response:
        return 451, "Requested action aborted. File system unavailable.", None

    if response.metadata.get("status") != "OK":
        error_msg = response.metadata.get("message", "Failed to open PASV data connection.")
        return 425, error_msg, session.to_json()

    ip = response.payload.get("ip")
    port = response.payload.get("port")

    if not ip or not port:
        return 425, "Failed to retrieve PASV connection details.", None

    session.enter_pasv_mode(ip, port)

    # Respuesta al cliente con el 227 indicando IP y puerto
    return 227, f"Entering Passive Mode ({ip.replace('.',',')},{port//256},{port%256}).", session.to_json()
