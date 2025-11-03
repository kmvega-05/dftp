from entities.file_system_manager import _GLOBAL_FSM as fs_manager, SecurityError


def handle_stat(command, client_socket, client_session):
    """Maneja comando STAT - Status del servidor o información de un archivo."""
    # Autenticación
    if not client_session.is_authenticated():
        client_session.send_response(client_socket, 530, "Not logged in")
        return

    # STAT <pathname> -> información del archivo
    if command.require_args(1):
        filename = command.get_arg(0)
        user_root = client_session.root_directory
        current_dir = client_session.current_directory

        try:
            info = fs_manager.stat(user_root, current_dir, filename)
        except SecurityError as e:
            client_session.send_response(client_socket, 550, str(e))
            return

        if info is None:
            client_session.send_response(client_socket, 550, "File not found")
            return

        if info.get('is_dir'):
            try:
                details = fs_manager.list_dir_detailed(user_root, current_dir, filename)
            except Exception as e:
                client_session.send_response(client_socket, 550, str(e))
                return

            lines = []
            for d in details:
                typ = 'd' if d.get('is_dir') else '-'
                size = d.get('size', 0)
                mtime = d.get('modified', '')
                name = d.get('name')
                lines.append(f"{typ} {size:>8} {mtime} {name}")

            message = ' | '.join(lines) if lines else ''
            client_session.send_response(client_socket, 213, message)
            return

        # Enviar información en una sola respuesta (usar 213) para reducir líneas
        parts = [
            f"Status of {filename}",
            f"Type: {'directory' if info.get('is_dir') else 'file'}",
            f"Size: {info.get('size', 0)} bytes",
            f"Modified: {info.get('modified')}",
            f"Permissions: {oct(info.get('permissions', 0))[-3:]}",
        ]
        message = ' | '.join(parts)
        client_session.send_response(client_socket, 213, message)
        return

    # STAT sin argumentos -> estado del servidor (multi-línea)
    if not command.require_args(1):
        status_lines = get_server_status(client_session)
        message = ' | '.join(["FTP server status:"] + status_lines)
        client_session.send_response(client_socket, 211, message)
        return


def get_server_status(client_session):
    """Genera información de estado del servidor para STAT sin argumentos."""
    return [
        f"Connected to {client_session.client_address[0]}:{client_session.client_address[1]}",
        f"Logged in as {client_session.username}",
        f"Current directory: {client_session.current_directory}",
        f"PASV mode: {'Active' if client_session.pasv_mode else 'Inactive'}",
        f"Authenticated: {client_session.authenticated}",
        f"Data connection: {'Open' if client_session.data_socket else 'Closed'}",
    ]