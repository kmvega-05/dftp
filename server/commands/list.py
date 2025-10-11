from entities.file_system import generate_directory_listing, get_user_root_directory

def handle_list(command, client_socket, server, client_session):
    """Maneja comando LIST - listar directorio"""
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    if not client_session.pasv_mode or not client_session.data_socket:
        server.send_response(client_socket, 425, "Use PASV first")
        return

    try:
        print("Waiting for data connection...")
        data_conn, data_addr = client_session.data_socket.accept()
        print(f"Data connection established with {data_addr}")

        server.send_response(client_socket, 150, "Here comes the directory listing")
        
        # Generar el listado
        user_root = get_user_root_directory(client_session.username)
        listing = generate_directory_listing(user_root, client_session.current_directory)
        
        # DEBUG: Imprimir el listado que se va a enviar
        print("=== LISTING TO SEND ===")
        print(listing)
        print("=== END LISTING ===")
        
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