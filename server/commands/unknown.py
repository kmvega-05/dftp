def handle_unknown(command, client_socket, server, client_session):
    """Maneja comandos desconocidos"""
    server.send_response(client_socket, 500, f"Command '{command.get_name()}' not recognized")