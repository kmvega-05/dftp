from entities.user_manager import validate_password


def handle_pass(command, client_socket, client_session):
    """Maneja comando PASS - validación de contraseña."""
    if not command.require_args(1):
        client_session.send_response(client_socket, 501, "Syntax error in parameters")
        return

    # Verificar que primero se envió USER
    if not client_session.username:
        client_session.send_response(client_socket, 503, "Login with USER first")
        return

    password = command.get_arg(0)

    # Validar la contraseña usando user_manager
    if validate_password(client_session.username, password):
        client_session.authenticate()
        client_session.send_response(client_socket, 230, "User logged in successfully")
    else:
        client_session.send_response(client_socket, 530, "Not logged in, password incorrect")