from server.modules.app.processing import Command

def handle_noop(cmd: Command, data: dict = None, processing_node = None) -> tuple[int, str, dict]:
    """Maneja comando NOOP - no operation (mantener conexión activa)."""
    if cmd.require_args(0):
        return 200, "NOOP OK", None
    else:
        return 501, "Syntax error in parameters", None