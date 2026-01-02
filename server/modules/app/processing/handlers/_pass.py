import logging
from server.modules.app.processing import Command
from server.modules.discovery import NodeType
from server.modules.app.routing import ClientSession
from server.modules.comm import Message, MessageType

logger = logging.getLogger("dftp.processing.handlers.pass")

def handle_pass(cmd: Command, data: dict = None, processing_node = None) -> tuple[int, str, dict]:
    """
    Maneja el comando PASS <password>.
    - Requiere que USER haya sido enviado antes.
    - Consulta a un AuthNode para validar username + password.
    - Autentica la sesión si es correcto.
    """

    # 1. Validación de sintaxis
    if not cmd.require_args(1):
        return 501, "Syntax error in parameters. Usage: PASS <password>", None

    # 2. Validación de sesión
    if not data:
        return 500, "Internal Error", None

    password = cmd.get_arg(0)
    session = ClientSession.from_json(data)

    # 3. Secuencia incorrecta: PASS antes de USER
    if not session.get_username():
        return 503, "Bad sequence of commands. Send USER first.", None

    # 4. Ya autenticado
    if session.is_authenticated():
        return 230, "Already logged in.", None

    # 5. Consultar nodos de autenticación
    auth_nodes = processing_node.query_by_role(NodeType.AUTH)
    if not auth_nodes:
        logger.warning("No AuthNodes found for PASS command")
        return 451, "User authentication not available.", None

    auth_response = None

    # 6. Validar password en los AuthNodes
    for auth_node in auth_nodes:
        try:
            query_msg = build_auth_password_query_msg(session.get_username(), password, processing_node.ip, auth_node["ip"])
            auth_response = processing_node.send_message(auth_node["ip"], 9000, query_msg, await_response=True)
            if auth_response is not None:
                break
        except Exception as e:
            logger.warning("Failed to contact AuthNode (%s) during PASS: %s", auth_node["ip"], e)
            continue

    # 7. Ningún AuthNode respondió
    if auth_response is None:
        logger.error("Unable to contact any AuthNode for PASS command")
        return 451, "User authentication not available.", None

    # 8. Password incorrecto
    if not auth_response.payload.get("result", False):
        return 530, "Login incorrect.", None

    # 9. Autenticación exitosa
    session.authenticate()
    return 230, "User logged in, proceed.", session.to_json()

def build_auth_password_query_msg(username: str, password: str, src: str = None, dst: str = None) -> Message:
    """Construye mensaje AUTH_VALIDATE_PASSWORD."""
    return Message(MessageType.AUTH_VALIDATE_PASSWORD, src, dst, payload={ "username": username, "password": password})
