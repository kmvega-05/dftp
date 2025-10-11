from entities.file_system import rename_path, get_user_root_directory

def handle_rnto(command, client_socket, server, client_session):
    """Maneja comando RNTO - Rename To"""
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    if not command.require_args(1):
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return

    # Verificar que primero se envió RNFR
    old_path = client_session.get_rename_from()
    if not old_path:
        server.send_response(client_socket, 503, "RNFR required first")
        return

    new_path = command.get_arg(0)
    user_root = get_user_root_directory(client_session.username)
    
    # Construir ruta completa para el nuevo nombre
    if new_path.startswith('/'):
        full_new_path = new_path
    else:
        full_new_path = client_session.current_directory + '/' + new_path
    
    # Renombrar
    success, message = rename_path(user_root, old_path, full_new_path)
    
    if success:
        server.send_response(client_socket, 250, message)
        print(f"RNTO successful: {old_path} -> {full_new_path}")
    else:
        server.send_response(client_socket, 550, message)
        print(f"RNTO failed: {message}")
    
    # Limpiar estado
    client_session.clear_rename_from()