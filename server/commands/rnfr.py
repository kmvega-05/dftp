from entities.file_system import get_user_root_directory, directory_exists, file_exists

def handle_rnfr(command, client_socket, server, client_session):
    """Maneja comando RNFR - Rename From"""
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    if not command.require_args(1):
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return

    old_path = command.get_arg(0)
    user_root = get_user_root_directory(client_session.username)
    
    # Construir ruta completa
    if old_path.startswith('/'):
        full_old_path = old_path
    else:
        full_old_path = client_session.current_directory + '/' + old_path
    
    # Verificar que existe (usando filesystem)
    if not directory_exists(user_root, full_old_path) and not file_exists(user_root, full_old_path):
        server.send_response(client_socket, 550, "File or directory not found")
        return
    
    # Guardar para RNTO
    client_session.set_rename_from(full_old_path)
    server.send_response(client_socket, 350, "Ready for destination name")
    print(f"RNFR: {full_old_path} - waiting for RNTO")