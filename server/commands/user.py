from entities.user_manager import user_exists


def handle_user(command, client_socket, client_session):
    """Maneja comando USER - autenticación de usuario."""
    if not command.require_args(1):
        client_session.send_response(client_socket, 501, "Syntax error in parameters")
        return

    username = command.get_arg(0)

    # Verificar si el usuario existe usando user_manager
    if user_exists(username):
        client_session.set_username(username)
        client_session.send_response(client_socket, 331, "User name okay, need password")
    else:
        client_session.send_response(client_socket, 530, "User not found")