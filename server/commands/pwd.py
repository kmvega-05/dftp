def handle_pwd(command, client_socket, server, client_session):
    """Maneja comando PWD - Print Working Directory"""
    if not command.require_args(0):
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return

    # Verificar autenticación (depende de si quieres que sea público o no)
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    # Obtener el directorio actual de la sesión
    current_dir = client_session.get_current_directory()
    
    # Enviar respuesta en formato FTP (257 "PATHNAME")
    server.send_response(client_socket, 257, f'"{current_dir}" is the current directory')