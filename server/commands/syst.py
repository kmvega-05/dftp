import platform

def get_system_info():
    """Obtiene información del sistema para el comando SYST"""
    system = platform.system().lower()
    
    if system == 'linux' or system == 'darwin':  # Darwin es macOS
        return "UNIX Type: L8"
    elif system == 'windows':
        return "Windows_NT"
    elif system == 'java':
        return "JVM"
    else:
        return "UNKNOWN Type: L8"

def handle_syst(command, client_socket, server, client_session):
    """Maneja comando SYST - información del sistema"""
    if command.require_args(0):
        system_info = get_system_info()
        server.send_response(client_socket, 215, system_info)
    else:
        server.send_response(client_socket, 501, "Syntax error in parameters")