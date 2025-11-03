from entities.file_system_manager import _GLOBAL_FSM as fs_manager, SecurityError


def handle_rnto(command, client_socket, client_session):
    """Maneja comando RNTO - Rename To (rename target path)."""
    # 1. Autenticación
    if not client_session.is_authenticated():
        client_session.send_response(client_socket, 530, "Not logged in")
        return

    # 2. Validar argumentos
    if not command.require_args(1):
        client_session.send_response(client_socket, 501, "Syntax error in parameters")
        return

    # 3. Verificar que se haya ejecutado RNFR previamente
    old_virtual_path = client_session.get_rename_from()
    if not old_virtual_path:
        client_session.send_response(client_socket, 503, "RNFR required first")
        return

    # 4. Obtener el nuevo path dado por el usuario
    requested_new_path = command.get_arg(0)
    user_root = client_session.root_directory 
    current_dir = client_session.current_directory

    try:
        fs_manager.rename(user_root, current_dir, old_virtual_path, requested_new_path)
    except (FileNotFoundError, FileExistsError, SecurityError) as e:
        client_session.send_response(client_socket, 550, str(e))
        client_session.clear_rename_from()
        return
    except Exception:
        client_session.send_response(client_socket, 451, "Requested action aborted. Local error in processing")
        client_session.clear_rename_from()
        return

    client_session.send_response(client_socket, 250, f'"{old_virtual_path}" renamed to "{requested_new_path}"')
    client_session.clear_rename_from()
