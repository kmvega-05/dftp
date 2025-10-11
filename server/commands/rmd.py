from entities.file_system import remove_directory, get_user_root_directory

def handle_rmd(command, client_socket, server, client_session):
    """Maneja comando RMD - Remove Directory"""
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    if not command.require_args(1):
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return

    dir_name = command.get_arg(0)
    user_root = get_user_root_directory(client_session.username)
    
    # Crear la ruta completa relativa al directorio actual
    if dir_name.startswith('/'):
        dir_path = dir_name
    else:
        dir_path = client_session.current_directory + '/' + dir_name
    
    # Eliminar el directorio
    success, message = remove_directory(user_root, dir_path)
    
    if success:
        server.send_response(client_socket, 250, message)
    else:
        server.send_response(client_socket, 550, message)