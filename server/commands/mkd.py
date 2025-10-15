from entities.file_system_manager import create_directory, get_user_root_directory

def handle_mkd(command, client_socket, server, client_session):
    """Maneja comando MKD - Make Directory"""

    # Chequea argumentos
    if not command.require_args(1):
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return
    
    # Valida autenticación
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    new_dir_name = command.get_arg(0)
    
    # Obtener directorio raíz y actual(para resolver rutas absolutas/relativas)
    user_root = get_user_root_directory(client_session.username)
    current_directory = client_session.get_current_directory()
    
    # Crea el directorio
    success, message = create_directory(user_root, current_directory, new_dir_name)
    
    if success:
        server.send_response(client_socket, 257, message)
    else:
        server.send_response(client_socket, 550, message)