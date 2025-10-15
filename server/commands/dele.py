from entities.file_system_manager import delete_file, get_user_root_directory

def handle_dele(command, client_socket, server, client_session):
    """Maneja comando DELE - Delete file"""

    # Chequear argumentos
    if not command.require_args(1):
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return
    
    # Verificar autenticación
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    filename = command.get_arg(0)
    
    # Obtener directorio raíz y actual(para resolver rutas absolutas/relativas)
    user_root = get_user_root_directory(client_session.username)
    current_directory = client_session.get_current_directory()
    
    # Eliminar el archivo
    success, message = delete_file(user_root, current_directory, filename)
    
    if success:
        server.send_response(client_socket, 250, message)
    else:
        server.send_response(client_socket, 550, message)