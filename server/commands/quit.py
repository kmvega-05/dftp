def handle_quit(command, client_socket, client_session):
    """Maneja comando QUIT según RFC-959.

    Si no hay transferencias en curso, responde 221 y el dispatcher puede
    cerrar la conexión inmediatamente. Si existen transferencias en curso,
    marca la petición como pendiente; la conexión se cerrará cuando las
    transferencias terminen.
    """

    if not command.require_args(0):
        client_session.send_response(client_socket, 501, "Syntax error in parameters")
        return

    can_close_now = client_session.request_quit()

    if can_close_now:
        # Cerrar inmediatamente
        client_session.send_response(client_socket, 221, "Goodbye")
    else:
        # Indicar que la petición fue recibida y será atendida cuando termine la transferencia
        client_session.send_response(client_socket, 200, "QUIT pending: will close after transfers complete")