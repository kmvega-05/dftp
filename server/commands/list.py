from entities.file_system_manager import _GLOBAL_FSM as fs_manager
import posixpath

def handle_list(command, client_socket, client_session):
    """Maneja comando LIST - listar directorio con formato detallado."""
    if not client_session.is_authenticated():
        client_session.send_response(client_socket, 530, "Not logged in")
        return

    # LIST puede tener 0 o 1 argumentos
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
        list_info = fs_manager.list_dir_detailed(user_root, current_directory, list_path)
    except Exception as e:
        client_session.send_response(client_socket, 550, str(e))
        return

    try:
        # Aceptar conexión de datos
        data_conn, _ = data_socket.accept()
        client_session.send_response(client_socket, 150, "Here comes the directory listing")

        lines = []
        for info in list_info:
            typ = 'd' if info.get('is_dir') else '-'
            size = info.get('size', 0)
            mtime = info.get('modified', '')
            name = info.get('name')
            lines.append(f"{typ} {size:>8} {mtime} {name}")

        listing = '\r\n'.join(lines) + '\r\n' if lines else ''
        data_conn.sendall(listing.encode('utf-8'))
        data_conn.close()

        client_session.send_response(client_socket, 226, "Directory send OK")

    except Exception:
        client_session.send_response(client_socket, 450, "Requested file action not taken")

    finally:
        client_session.cleanup_pasv()