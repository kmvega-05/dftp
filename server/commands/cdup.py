from entities.file_system_manager import change_directory, get_user_root_directory

def handle_cdup(command, client_socket, server, client_session):
    """Maneja comando CDUP - Change to Parent Directory"""
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    if not command.require_args(0):
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return

    user_root = get_user_root_directory(client_session.username)
    current_dir = client_session.get_current_directory()
    
    # Cambiar al directorio padre
    new_current_dir = change_directory(user_root, current_dir, "..")
    
    if new_current_dir:
        client_session.current_directory = new_current_dir
        server.send_response(client_socket, 200, f'Directory changed to parent directory "{new_current_dir}"')
    else:
        server.send_response(client_socket, 550, "Failed to change to parent directory")