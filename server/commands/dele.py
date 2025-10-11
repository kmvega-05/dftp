from entities.file_system import delete_file, get_user_root_directory

def handle_dele(command, client_socket, server, client_session):
    """Maneja comando DELE - Delete file"""
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    if not command.require_args(1):
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return

    filename = command.get_arg(0)
    user_root = get_user_root_directory(client_session.username)
    
    # Construir ruta completa
    if filename.startswith('/'):
        file_path = filename
    else:
        file_path = client_session.current_directory + '/' + filename
    
    # Eliminar el archivo
    success, message = delete_file(user_root, file_path)
    
    if success:
        server.send_response(client_socket, 250, message)
    else:
        server.send_response(client_socket, 550, message)