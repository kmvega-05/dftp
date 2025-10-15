from entities.file_system_manager import get_user_root_directory, change_directory

def handle_cwd(command, client_socket, server, client_session):
    """Maneja comando CWD - Change Working Directory"""
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    if not command.require_args(1):
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return

    new_directory = command.get_arg(0)
    user_root_directory = get_user_root_directory(client_session.username)
    current_directory = client_session.get_current_directory()
    
    new_current_dir = change_directory(user_root_directory, current_directory, new_directory)
    
    if new_current_dir:
        client_session.current_directory = new_current_dir
        server.send_response(client_socket, 250, f'Directory changed to "{new_current_dir}"')
    else:
        server.send_response(client_socket, 550, "Failed to change directory")
