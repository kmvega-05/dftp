import platform

# Constantes para mejorar la legibilidad
SYSTEM_MAPPINGS = {
    'linux': "UNIX Type: L8",
    'darwin': "UNIX Type: L8",  # macOS
    'windows': "Windows_NT",
    'java': "JVM"
}

DEFAULT_SYSTEM_INFO = "UNKNOWN Type: L8"

def get_system_info():
    """Obtiene información del sistema para el comando SYST"""
    system = platform.system().lower()
    return SYSTEM_MAPPINGS.get(system, DEFAULT_SYSTEM_INFO)

def handle_syst(command, client_socket, server, client_session):
    """Maneja comando SYST - información del sistema"""
    if not command.require_args(0):
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return
    
    system_info = get_system_info()
    server.send_response(client_socket, 215, system_info)