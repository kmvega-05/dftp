from entities.file_system_manager import get_user_root_directory, directory_exists, file_exists, secure_path_resolution, SecurityError

def handle_rnfr(command, client_socket, server, client_session):
    """Maneja comando RNFR - Rename From"""

    # Chequear argumentos
    if not command.require_args(1):
        server.send_response(client_socket, 501, "Syntax error in parameters or arguments")
        return
    
    # Validar autenticación
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    old_path = command.get_arg(0)
    username = client_session.username
    user_root = get_user_root_directory(username)
    current_dir = client_session.current_directory

    try:
        # Verificar existencia del archivo o directorio a renombrar
        if not directory_exists(user_root, current_dir, old_path) and not file_exists(user_root, current_dir, old_path):
            server.send_response(client_socket, 550, "File or directory not found")
            return
        
        # Guardar el path para proximo rename_to 
        client_session.set_rename_from(secure_path_resolution(user_root, current_dir, old_path))

        server.send_response(client_socket, 350, "Ready for destination name")
        print(f"[RNFR] {username}: '{old_path}' → awaiting RNTO")
        print(f"Rute to rename : {client_session.get_rename_from()}")

    except SecurityError:
        server.send_response(client_socket, 550, "Security violation: path traversal detected")
        return

    except Exception as e:
        print(f"Error in RNFR: {e}")
        server.send_response(client_socket, 451, "Requested action aborted. Local error in processing")
        return
