def handle_rein(command, client_socket, client_session):
    """Maneja comando REIN - reinicializa la sesión FTP."""

    if command.require_args(0):
        client_session.reinitialize()

        client_session.send_response(client_socket, 220, "Service ready for new user")
    else:
        client_session.send_response(client_socket, 501, "Syntax error in parameters")