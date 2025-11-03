import os
from entities.file_system_manager import _GLOBAL_FSM as fs_manager, SecurityError


def handle_rnfr(command, client_socket, client_session):
    """Maneja comando RNFR - Rename From"""

    # Chequear argumentos
    if not command.require_args(1):
        client_session.send_response(client_socket, 501, "Syntax error in parameters or arguments")
        return

    # Validar autenticación
    if not client_session.is_authenticated():
        client_session.send_response(client_socket, 530, "Not logged in")
        return

    old_path = command.get_arg(0)
    user_root = client_session.root_directory
    current_dir = client_session.current_directory

    try:
        virtual, _ = fs_manager.exists(user_root, current_dir, old_path, want='any')
    except SecurityError as e:
        client_session.send_response(client_socket, 550, str(e))
        return
    except FileNotFoundError:
        client_session.send_response(client_socket, 550, "File or directory not found")
        return

    # Guardar la ruta virtual para el siguiente RNTO
    client_session.set_rename_from(virtual)
    client_session.send_response(client_socket, 350, "Ready for destination name")
