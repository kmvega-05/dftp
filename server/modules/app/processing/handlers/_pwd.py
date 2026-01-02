from server.modules.app.processing import Command
from server.modules.app.routing import ClientSession

def handle_pwd(cmd: Command, data: dict = None, processing_node  = None) -> tuple[int, str, dict]:
    """Maneja comando PWD - imprimir directorio actual."""
    try:
        if not cmd.require_args(0):
            return 501, "Syntax error in parameters.", None

        if not data:
            return 530, "Not logged in.", None

        session = ClientSession.from_json(data)

        if not session.is_authenticated():
            return 530, "Not logged in.", None

        return 257, f"\"{session.get_cwd()}\" is the current directory.", None

    except Exception:
        return 451, "Internal Server Error.", None
