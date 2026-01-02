import logging
from server.modules.app.processing import Command
from server.modules.discovery import NodeType
from server.modules.app.routing import ClientSession
from server.modules.comm import Message, MessageType
logger = logging.getLogger("dftp.processing.handlers.user")

def handle_user(cmd: Command, data: dict = None, processing_node = None) -> tuple[int, str, dict]:
    """Maneja el comando USER <username>."""

    # 1. Validar argumentos
    if not cmd.require_args(1):
        return 501, "Syntax error in parameters. Usage: USER <username>", None

    # 2. Validar que exista la sesión
    if data is None:
        return 500, "Internal Error", None

    # 3. Extraer username y sesión
    username = cmd.get_arg(0)
    session = ClientSession.from_json(data)

    # 4. Consultar nodos de autenticación disponibles
    auth_nodes = processing_node.query_by_role(NodeType.AUTH)
    if not auth_nodes:
        logger.warning("No AuthNodes found for USER command")
        return 451, "User authentication not available.", None

    auth_response = None

    # 5. Intentar validar usuario con cada AuthNode hasta obtener respuesta
    for auth_node in auth_nodes:
        try:
            query_msg = build_auth_user_query_msg(username, processing_node.ip, auth_node["ip"])
            auth_response = processing_node.send_message(auth_node["ip"], 9000, query_msg, await_response=True)
            if auth_response is not None:
                break
        except Exception as e:
            logger.warning("Failed to contact AuthNode (%s): %s", auth_node["ip"], e)
            continue

    # 6. Ningún AuthNode respondió
    if auth_response is None:
        logger.error("Unable to contact any AuthNode for USER command")
        return 451, "User authentication not available.", None

    # 7. Usuario no válido
    if not auth_response.payload.get("result", False):
        return 530, "User not found.", None

    # 8. Usuario válido: actualizar sesión
    session.change_user(username)
    return 331, f"User {username} accepted, please provide password.", session.to_json()


def build_auth_user_query_msg(username : str = "", src : str = None, dst : str = None) -> Message:
    return Message(MessageType.AUTH_VALIDATE_USER, src, dst, payload={"username": username})