from entities.file_system_manager import _GLOBAL_FSM as fs_manager

def handle_nlst(command, client_socket, client_session):
    """Maneja comando NLST - lista solo nombres de archivos"""
    if not client_session.is_authenticated():
        client_session.send_response(client_socket, 530, "Not logged in")
        return

    # NLST puede tener 0 o 1 argumentos
    if command.arg_count() > 1:
        client_session.send_response(client_socket, 501, "Syntax error in parameters")
        return

    data_socket, _ = client_session.get_pasv_info()
    if not data_socket:
        client_session.send_response(client_socket, 425, "Use PASV first")
        return

    list_path = command.get_arg(0) if command.arg_count() == 1 else "."
    user_root = client_session.root_directory
    current_directory = client_session.current_directory

    try:
        names = fs_manager.list_dir(user_root, current_directory, list_path)
    except Exception as e:
        client_session.send_response(client_socket, 550, str(e))
        return

    try:
        data_conn, _ = data_socket.accept()
        client_session.send_response(client_socket, 150, "Here comes the directory listing")

        file_list = '\r\n'.join(names) + '\r\n' if names else ''
        data_conn.sendall(file_list.encode('utf-8'))
        data_conn.close()
        client_session.send_response(client_socket, 226, "Directory send OK")

    except Exception:
        client_session.send_response(client_socket, 450, "Requested file action not taken")

    finally:
        client_session.cleanup_pasv()