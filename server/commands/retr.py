from entities.file_system import retrieve_file, get_user_root_directory

def handle_retr(command, client_socket, server, client_session):
    """Maneja comando RETR - descargar archivo con streaming"""
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    if not command.require_args(1):
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return

    if not client_session.pasv_mode or not client_session.data_socket:
        server.send_response(client_socket, 425, "Use PASV first")
        return

    filename = command.get_arg(0)
    user_root = get_user_root_directory(client_session.username)
    
    # Construir ruta completa
    if filename.startswith('/'):
        file_path = filename
    else:
        file_path = client_session.current_directory + '/' + filename

    try:
        # Aceptar conexión de datos
        print("Waiting for data connection for file download...")
        data_conn, data_addr = client_session.data_socket.accept()
        print(f"Data connection established with {data_addr}")

        # Enviar respuesta preliminar
        server.send_response(client_socket, 150, f"Opening data connection for {filename}")

        # Usar streaming (pasa data_conn para enviar por chunks)
        success, message = retrieve_file(user_root, file_path, data_conn)
        data_conn.close()
        
        if success:
            server.send_response(client_socket, 226, message)
            print(f"RETR successful: {message}")
        else:
            server.send_response(client_socket, 550, message)
            print(f"RETR failed: {message}")
        
    except Exception as e:
        print(f"Error in RETR command: {e}")
        server.send_response(client_socket, 450, "Requested file action not taken")
    
    finally:
        client_session.cleanup_pasv()