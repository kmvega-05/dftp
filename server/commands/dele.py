from entities.file_system_manager import _GLOBAL_FSM as fs_manager, SecurityError


def handle_dele(command, client_socket, client_session):
    """Maneja comando DELE - Delete file"""

    # Chequear argumentos
    if not command.require_args(1):
        client_session.send_response(client_socket, 501, "Syntax error in parameters")
        return

    # Verificar autenticación
    if not client_session.is_authenticated():
        client_session.send_response(client_socket, 530, "Not logged in")
        return

    filename = command.get_arg(0)
    user_root = client_session.root_directory
    current_directory = client_session.current_directory

    try:
        success, message = fs_manager.delete_file(user_root, current_directory, filename)
    except FileNotFoundError:
        client_session.send_response(client_socket, 550, "File not found")
        return
    except IsADirectoryError:
        client_session.send_response(client_socket, 550, "Not a file")
        return
    except SecurityError as e:
        client_session.send_response(client_socket, 550, str(e))
        return
    except Exception:
        client_session.send_response(client_socket, 451, "Requested action aborted. Local error in processing")
        return

    client_session.send_response(client_socket, 250, message)