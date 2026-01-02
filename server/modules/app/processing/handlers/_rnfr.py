import logging
from server.modules.app.processing import Command
from server.modules.app.routing import ClientSession



logger = logging.getLogger("dftp.processing.handlers.rnfr")

def handle_rnfr(cmd: Command, data: dict = None, processing_node=None) -> tuple[int, str, dict]:
    """RNFR <path> - inicia un renombrado de archivo o directorio."""

    if not cmd.require_args(1):
        return 501, "Syntax error in parameters. Usage: RNFR <path>", None

    if not data:
        return 500, "Internal server error.", None

    session = ClientSession.from_json(data)

    if not session.is_authenticated():
        return 530, "Not logged in.", None

    source_path = cmd.get_arg(0)

    # Guardar origen para RNTO (sobrescribe cualquier RNFR previo)
    session.set_rename_from(source_path)

    return 350, f"File or directory '{source_path}' ready for renaming.", session.to_json()
