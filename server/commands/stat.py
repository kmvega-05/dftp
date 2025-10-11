
from entities.file_system import get_file_status, get_user_root_directory

def handle_stat(command, client_socket, server, client_session):
    """Maneja comando STAT - Status del servidor o archivo"""
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    # STAT sin argumentos - estado del servidor
    if command.require_args(0):
        status_info = get_server_status(client_session)
        
        # Enviar respuesta multi-línea
        server.send_response(client_socket, 211, "FTP server status:")
        for line in status_info:
            client_socket.send(f" {line}\r\n".encode('utf-8'))
        server.send_response(client_socket, 211, "End of status")
        
    # STAT con argumentos - información de archivo
    elif command.require_args(1):
        filename = command.get_arg(0)
        user_root = get_user_root_directory(client_session.username)
        
        # Construir ruta completa
        if filename.startswith('/'):
            file_path = filename
        else:
            file_path = client_session.current_directory + '/' + filename
        
        # Obtener información del archivo
        file_info, message = get_file_status(user_root, file_path)
        
        if file_info is None:
            server.send_response(client_socket, 550, message)
            return
        
        # Formatear respuesta
        status_lines = [
            f"Status of {filename}:",
            f"    Type: {file_info['type']}",
            f"    Size: {file_info['size']} bytes",
            f"    Modified: {file_info['modified']}",
            f"    Permissions: {oct(file_info['permissions'])[-3:]}",
        ]
        
        server.send_response(client_socket, 213, status_lines[0])
        for line in status_lines[1:]:
            client_socket.send(f" {line}\r\n".encode('utf-8'))
        server.send_response(client_socket, 213, "End of status")
        
    else:
        server.send_response(client_socket, 501, "Syntax error in parameters")

def get_server_status(client_session):
    """Genera información de estado del servidor"""
    status_lines = [
        f"Connected to {client_session.client_address[0]}:{client_session.client_address[1]}",
        f"Logged in as {client_session.username}",
        f"Current directory: {client_session.current_directory}",
        f"PASV mode: {'Active' if client_session.pasv_mode else 'Inactive'}",
        f"Authenticated: {client_session.authenticated}",
        f"Data connection: {'Open' if client_session.data_socket else 'Closed'}",
    ]
    return status_lines