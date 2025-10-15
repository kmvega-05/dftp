from entities.file_system_manager import list_directory_names, get_user_root_directory

def handle_nlst(command, client_socket, server, client_session):
    """Maneja comando NLST - lista solo nombres de archivos"""
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    # NLST puede tener 0 o 1 argumentos
    if command.arg_count() > 1:
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return

    if not client_session.pasv_mode or not client_session.data_socket:
        server.send_response(client_socket, 425, "Use PASV first")
        return

    try:
        # Aceptar conexión de datos primero
        print("Waiting for data connection...")
        data_conn, data_addr = client_session.data_socket.accept()
        print(f"Data connection established with {data_addr}")

        # Obtener el path a listar (si se proporciona)
        list_path = command.get_arg(0) if command.arg_count() == 1 else "."
        
        # Obtener lista de nombres usando nuevo file_system_manager
        user_root = get_user_root_directory(client_session.username)
        current_directory = client_session.get_current_directory()
        
        file_names = list_directory_names(user_root, current_directory, list_path)
        
        if file_names is None:
            data_conn.close()
            server.send_response(client_socket, 550, "Directory not found")
            return

        # Convertir lista a string con formato (un nombre por línea)
        file_list = file_list_to_string(file_names)
        
        # DEBUG: Imprimir la lista que se va a enviar
        print("=== NLST TO SEND ===")
        print(file_list)
        print("=== END NLST ===")

        server.send_response(client_socket, 150, "Here comes the directory listing")
        
        # Enviar lista por conexión de datos
        data_conn.send(file_list.encode('utf-8'))
        data_conn.close()
        print("Name listing sent, data connection closed")
        
        server.send_response(client_socket, 226, "Directory send OK")
        
    except Exception as e:
        print(f"Error in NLST command: {e}")
        server.send_response(client_socket, 450, "Requested file action not taken")
    
    finally:
        client_session.cleanup_pasv()


def file_list_to_string(file_names):
    """Convierte lista de nombres de archivos a string con formato (un nombre por línea)"""
    return "\r\n".join(file_names) + "\r\n" if file_names else ""