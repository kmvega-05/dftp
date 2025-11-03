import os
from entities.file_system_manager import _GLOBAL_FSM as fs_manager, SecurityError


def handle_cwd(command, client_socket, client_session):
    """Maneja comando CWD - Change Working Directory"""

    # Chequear argumentos
    if not command.require_args(1):
        client_session.send_response(client_socket, 501, "Syntax error in parameters")
        return

    # Verificar autenticación
    if not client_session.is_authenticated():
        client_session.send_response(client_socket, 530, "Not logged in")
        return

    new_directory = command.get_arg(0)

    # Obtener directorio raíz y actual
    user_root = client_session.root_directory
    current_directory = client_session.current_directory

    try:
        virtual, _ = fs_manager.exists(user_root, current_directory, new_directory, want='dir')
    except SecurityError as e:
        client_session.send_response(client_socket, 550, str(e))
        return
    except FileNotFoundError:
        client_session.send_response(client_socket, 550, "Directory not found")
        return
    except NotADirectoryError:
        client_session.send_response(client_socket, 550, "Not a directory")
        return

    client_session.current_directory = virtual
    client_session.send_response(client_socket, 250, f'Directory changed to "{virtual}"')
