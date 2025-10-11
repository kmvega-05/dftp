import socket
from entities.file_system import store_file_optimized, get_user_root_directory

def handle_stor(command, client_socket, server, client_session):
    """Maneja comando STOR - almacenar archivo desde el cliente"""
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
        print("Waiting for data connection for file upload...")
        data_conn, data_addr = client_session.data_socket.accept()
        print(f"Data connection established with {data_addr}")

        # Enviar respuesta preliminar
        server.send_response(client_socket, 150, "Ready to receive file")
        
        # Usar sistema optimizado híbrido
        success, message = store_file_optimized(user_root, file_path, data_conn)
        data_conn.close()
        
        if success:
            server.send_response(client_socket, 226, message)
            print(f"File stored successfully: {file_path}")
        else:
            server.send_response(client_socket, 550, message)
            print(f"Failed to store file: {message}")
        
    except Exception as e:
        print(f"Error in STOR command: {e}")
        server.send_response(client_socket, 450, "Requested file action not taken")
    
    finally:
        client_session.cleanup_pasv()