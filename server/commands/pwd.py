def handle_pwd(command, client_socket, client_session):
    """Maneja comando PWD - Print Working Directory"""

    # Chequear argumentos
    if not command.require_args(0):
        client_session.send_response(client_socket, 501, "Syntax error in parameters")
        return

    # Verificar autenticación
    if not client_session.is_authenticated():
        client_session.send_response(client_socket, 530, "Not logged in")
        return

    # Obtener el directorio actual de la sesión
    current_dir = client_session.current_directory

    # Enviar respuesta en formato FTP (257 "PATHNAME")
    client_session.send_response(client_socket, 257, f'"{current_dir}" is the current directory')