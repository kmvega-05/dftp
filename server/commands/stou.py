from entities.file_system_manager import (
    store_file_optimized, 
    get_user_root_directory, 
    generate_unique_filename, 
    secure_path_resolution, 
    get_real_filesystem_path, 
    SecurityError)

def handle_stou(command, client_socket, server, client_session):
    """Maneja comando STOU (Store Unique) - Guarda un archivo con nombre único"""
    
    # Verificar autenticación
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    # Verificar modo pasivo activo
    if not client_session.pasv_mode or not client_session.data_socket:
        server.send_response(client_socket, 425, "Use PASV first")
        return

    # STOU puede tener 0 o 1 argumentos (nombre sugerido)
    original_filename = command.get_arg(0) if command.has_args() else "file"
    user_root = get_user_root_directory(client_session.username)

    try:
        # Generar nombre único y construir ruta segura
        unique_filename = generate_unique_filename(user_root, original_filename)
        virtual_path = secure_path_resolution(user_root, client_session.current_directory, unique_filename)
        real_path = get_real_filesystem_path(user_root, virtual_path)

        # Aceptar conexión de datos
        print("Waiting for data connection for STOU upload...")
        data_conn, data_addr = client_session.data_socket.accept()
        print(f"Data connection established with {data_addr}")

        # Enviar respuesta preliminar con el nombre único
        server.send_response(client_socket, 150, f'File: {unique_filename}')

        # Guardar archivo
        success, message = store_file_optimized(user_root, real_path, data_conn)
        data_conn.close()

        if success:
            # RFC 959 indica que STOU responde con 250 al completar correctamente
            server.send_response(client_socket, 250, f'{unique_filename}')
            print(f"File stored with unique name: {unique_filename}")
        else:
            server.send_response(client_socket, 550, message)
            print(f"Failed to store file: {message}")

    except SecurityError:
        server.send_response(client_socket, 550, "Path traversal attempt detected")
        print("SecurityError: Path traversal detected during STOU")
    except Exception as e:
        print(f"Error in STOU command: {e}")
        server.send_response(client_socket, 450, "Requested file action not taken")

    finally:
        client_session.cleanup_pasv()