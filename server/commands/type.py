def handle_type(command, client_socket, server, client_session):
    """Maneja comando TYPE - configurar tipo de transferencia"""
    if not command.require_args(1):
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return

    type_code = command.get_arg(0).upper()
    
    # Soporte para los tipos más comunes
    if type_code == 'A':
        # ASCII mode
        server.send_response(client_socket, 200, "Type set to ASCII")
    elif type_code == 'I':
        # Binary/Image mode
        server.send_response(client_socket, 200, "Type set to binary")
    else:
        # Tipo no soportado
        server.send_response(client_socket, 504, "Type not implemented")