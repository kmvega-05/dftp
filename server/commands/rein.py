def handle_rein(command, client_socket, server, client_session):
    """Maneja comando REIN - reinicializa la sesión FTP"""
    if command.require_args(0):
        # Usar el método de reset de la sesión
        client_session.reset_session()
        server.send_response(client_socket, 220, "Service ready for new user")
    else:
        server.send_response(client_socket, 501, "Syntax error in parameters")