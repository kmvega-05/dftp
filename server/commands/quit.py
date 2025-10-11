def handle_quit(command, client_socket, server, client_session):
    """Maneja comando QUIT - cierra la conexión FTP"""
    if command.require_args(0):
        server.send_response(client_socket, 221, "Goodbye")
        # La conexión se cerrará en handle_client después de esta respuesta
    else:
        server.send_response(client_socket, 501, "Syntax error in parameters")