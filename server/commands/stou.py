import socket
from entities.file_system import store_file_optimized, get_user_root_directory, generate_unique_filename

def handle_stou(command, client_socket, server, client_session):
    """Maneja comando STOU - Store Unique"""
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    if not client_session.pasv_mode or not client_session.data_socket:
        server.send_response(client_socket, 425, "Use PASV first")
        return

    # STOU puede tener 0 o 1 argumentos (nombre sugerido)
    original_filename = command.get_arg(0) if command.has_args() else "file"
    user_root = get_user_root_directory(client_session.username)
    
    # Generar nombre único
    unique_filename = generate_unique_filename(user_root, original_filename)
    file_path = client_session.current_directory + '/' + unique_filename

    try:
        # Aceptar conexión de datos
        print("Waiting for data connection for STOU upload...")
        data_conn, data_addr = client_session.data_socket.accept()
        print(f"Data connection established with {data_addr}")

        # Enviar respuesta preliminar con el nombre único
        server.send_response(client_socket, 150, f'File: {unique_filename}')
        
        # Almacenar el archivo
        success, message = store_file_optimized(user_root, file_path, data_conn)
        data_conn.close()
        
        if success:
            # STOU responde con 250 (no 226) y el nombre único
            server.send_response(client_socket, 250, f'{unique_filename}')
            print(f"File stored with unique name: {unique_filename}")
        else:
            server.send_response(client_socket, 550, message)
            print(f"Failed to store file: {message}")
        
    except Exception as e:
        print(f"Error in STOU command: {e}")
        server.send_response(client_socket, 450, "Requested file action not taken")
    
    finally:
        client_session.cleanup_pasv()