from entities.file_system_manager import _GLOBAL_FSM as fs_manager, SecurityError
import os


def handle_cdup(command, client_socket, client_session):
    """Maneja comando CDUP - Change to Parent Directory"""

    # Chequear argumentos
    if not command.require_args(0):
        client_session.send_response(client_socket, 501, "Syntax error in parameters")
        return

    # Verificar autenticación 
    if not client_session.is_authenticated():
        client_session.send_response(client_socket, 530, "Not logged in")
        return

    # Obtener directorio raiz y actual
    user_root = client_session.root_directory
    current_dir = client_session.current_directory

    try:
        virtual, _ = fs_manager.exists(user_root, current_dir, "..", want='dir')
    except SecurityError as e:
        client_session.send_response(client_socket, 550, str(e))
        return
    except FileNotFoundError:
        client_session.send_response(client_socket, 550, "Parent directory not found")
        return
    except NotADirectoryError:
        client_session.send_response(client_socket, 550, "Parent is not a directory")
        return

    client_session.current_directory = virtual
    client_session.send_response(client_socket, 250, f'Directory changed to "{virtual}"')