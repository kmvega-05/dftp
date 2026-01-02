from server.modules.app.processing import Command
from server.modules.app.routing import ClientSession

def handle_rein(cmd: Command, data: dict = None, processing_node = None) -> tuple[int, str, dict]:
    """REIN: Reinitialize. Resetea la sesión del usuario, cerrando auth, cwd, renombrado y modo pasivo."""

    # 1. Validación de argumentos
    if not cmd.require_args(0):
        return 501, "Syntax error in parameters.", None

    # 2. Validación de sesión
    if not data:
        return 500, "Internal Error.", None

    # 3. Reconstruir y resetear la sesión
    session = ClientSession.from_json(data)
    session.reset_session()

    # 4. Retorno: 220 = Service ready
    return 220, "Session reinitialized.", session.to_json()