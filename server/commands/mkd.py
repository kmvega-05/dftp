from entities.file_system import create_directory, get_user_root_directory

def handle_mkd(command, client_socket, server, client_session):
    """Maneja comando MKD - Make Directory"""
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    if not command.require_args(1):
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return

    new_dir_name = command.get_arg(0)
    user_root = get_user_root_directory(client_session.username)
    
    # Crear la ruta completa relativa al directorio actual
    if new_dir_name.startswith('/'):
        dir_path = new_dir_name
    else:
        dir_path = client_session.current_directory + '/' + new_dir_name
    
    # Crear el directorio
    success, message = create_directory(user_root, dir_path)
    
    if success:
        server.send_response(client_socket, 257, message)
    else:
        server.send_response(client_socket, 550, message)