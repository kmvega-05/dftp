def handle_noop(command, client_socket, client_session):
    """Maneja comando NOOP - no operation (mantener conexión activa)."""

    if command.require_args(0):
        client_session.send_response(client_socket, 200, "NOOP ok")
    else:
        client_session.send_response(client_socket, 501, "Syntax error in parameters")