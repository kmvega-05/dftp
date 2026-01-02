from server.modules.app.processing import Command

def handle_quit(cmd: Command, data: dict = None, processing_node = None) -> tuple[int, str, dict]:
    """Maneja comando QUIT - cerrar sesión."""
    if not cmd.require_args(0):
        return 501, "Syntax error in parameters.", None 
    
    return 221, "Goodbye.", None