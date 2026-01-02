import platform
from server.modules.app.processing import Command

DEFAULT_SYSTEM_INFO = "UNKNOWN Type: L8"
SYSTEM_MAPPINGS = { 'linux': "UNIX Type: L8", 'darwin': "UNIX Type: L8", 'windows': "Windows_NT", 'java': "JVM"}

def handle_syst(cmd: Command, data: dict = None, processing_node = None) -> tuple[int, str, dict]:
    """Maneja comando SYST - información del sistema."""
    
    if not cmd.require_args(0):
        return 501, "Syntax error in parameters", None
    
    system_info = get_system_info()
    return 215, system_info, None

def get_system_info():
    """Obtiene información del sistema para el comando SYST"""
    system = platform.system().lower()
    return SYSTEM_MAPPINGS.get(system, DEFAULT_SYSTEM_INFO)

