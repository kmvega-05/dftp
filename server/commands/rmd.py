from entities.file_system_manager import _GLOBAL_FSM as fs_manager, SecurityError

def handle_rmd(command, client_socket, client_session):
    """Maneja comando RMD - Remove Directory (RFC-959)."""

    # Chequea argumentos
    if not command.require_args(1):
        client_session.send_response(client_socket, 501, "Syntax error in parameters")
        return

    # Valida autenticación
    if not client_session.is_authenticated():
        client_session.send_response(client_socket, 530, "Not logged in")
        return

    dir_name = command.get_arg(0)

    # Obtener directorio raíz y actual
    user_root = client_session.root_directory
    current_directory = client_session.current_directory

    try:
        success, message = fs_manager.remove_dir(user_root, current_directory, dir_name)
    except FileNotFoundError:
        client_session.send_response(client_socket, 550, "Directory does not exist")
        return
    except NotADirectoryError:
        client_session.send_response(client_socket, 550, "Not a directory")
        return
    except OSError as e:
        # Directory not empty or other OS errors
        client_session.send_response(client_socket, 550, str(e))
        return
    except SecurityError as e:
        client_session.send_response(client_socket, 550, str(e))
        return

    client_session.send_response(client_socket, 250, message)