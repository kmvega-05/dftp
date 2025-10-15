from entities.file_system_manager import list_directory_detailed, get_user_root_directory

def handle_list(command, client_socket, server, client_session):
    """Maneja comando LIST - listar directorio con formato detallado"""
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    # LIST puede tener 0 o 1 argumentos
    if command.arg_count() > 1:
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return

    if not client_session.pasv_mode or not client_session.data_socket:
        server.send_response(client_socket, 425, "Use PASV first")
        return

    try:
        
        # Aceptar conexión de datos
        print("Waiting for data connection...")
        data_conn, data_addr = client_session.data_socket.accept()
        print(f"Data connection established with {data_addr}")

        # Obtener el path a listar (si se proporciona)
        list_path = command.get_arg(0) if command.arg_count() == 1 else "."
        
        # Generar el listado ANTES de aceptar la conexión de datos
        user_root = get_user_root_directory(client_session.username)
        current_directory = client_session.get_current_directory()
        
        listing = list_directory_detailed(user_root, current_directory, list_path)
        
        if listing is None:
            server.send_response(client_socket, 550, "Directory not found")
            return

        # DEBUG: Imprimir el listado que se va a enviar
        print("=== LISTING TO SEND ===")
        print(listing)
        print("=== END LISTING ===")

        server.send_response(client_socket, 150, "Here comes the directory listing")
        
        # Enviar listado por conexión de datos
        data_conn.send(listing.encode('utf-8'))
        data_conn.close()
        print("Directory listing sent, data connection closed")
        
        server.send_response(client_socket, 226, "Directory send OK")
        
    except Exception as e:
        print(f"Error in LIST command: {e}")
        server.send_response(client_socket, 450, "Requested file action not taken")
    
    finally:
        client_session.cleanup_pasv()