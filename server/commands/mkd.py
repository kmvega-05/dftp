from entities.file_system_manager import _GLOBAL_FSM as fs_manager, SecurityError

def handle_mkd(command, client_socket, client_session):
    """Maneja comando MKD - Make Directory (RFC-959).

    Crea un directorio relativo al current_directory del usuario o una ruta
    absoluta dentro del root del usuario.
    """
    # Chequea argumentos
    if not command.require_args(1):
        client_session.send_response(client_socket, 501, "Syntax error in parameters")
        return

    # Valida autenticación
    if not client_session.is_authenticated():
        client_session.send_response(client_socket, 530, "Not logged in")
        return

    new_dir_name = command.get_arg(0)

    # Obtener directorio raíz y actual (resolverá paths virtuales)
    user_root = client_session.root_directory 
    current_directory = client_session.current_directory

    # Crea el directorio usando FileSystemManager
    try:
        success, message = fs_manager.make_dir(user_root, current_directory, new_dir_name)
    except FileExistsError as e:
        client_session.send_response(client_socket, 550, str(e))
        return
    except SecurityError as e:
        client_session.send_response(client_socket, 550, str(e))
        return
    except Exception:
        client_session.send_response(client_socket, 451, "Requested action aborted. Local error in processing")
        return

    client_session.send_response(client_socket, 257, message)