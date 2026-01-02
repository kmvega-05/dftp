from server.modules.app.processing import Command
from server.modules.app.routing import ClientSession

def handle_type(cmd: Command, data: dict = None, processing_node = None) -> tuple[int, str, dict]:
    """
    Maneja el comando TYPE.
    Cambia el tipo de transferencia (ASCII, Binary, etc.).
    """
    if not cmd.require_args(1):
        return 501, "Syntax error in parameters.", None
    
    if not data:
        return 530, "Not logged in.", None

    # Reconstruir sesión desde el dict recibido
    session = ClientSession.from_json(data)
    t = cmd.get_arg(0).upper()

    # Validar tipo
    if t not in ("A", "I", "E", "L"):
        return 504, "Command not implemented for that parameter.", None

    # Aplicar cambio de tipo
    session.set_transfer_type(t)

    return 200, f"Type set to {t}.", session.to_json()
