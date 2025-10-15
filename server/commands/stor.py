import socket
from entities.file_system_manager import store_file_optimized, get_user_root_directory, secure_path_resolution

def handle_stor(command, client_socket, server, client_session):
    """Maneja comando STOR - almacena un archivo recibido del cliente mediante data connection."""

    # 1. Validación de sesión y argumentos
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    if not command.require_args(1):
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return

    # 2. Validar modo PASV y socket de datos
    if not client_session.pasv_mode or not client_session.data_socket:
        server.send_response(client_socket, 425, "Use PASV first")
        return

    filename = command.get_arg(0)
    user_root = get_user_root_directory(client_session.username)

    try:
        # Resolución segura de la ruta
        virtual_path = secure_path_resolution(user_root, client_session.current_directory, filename)

    except ValueError as e:
        server.send_response(client_socket, 550, str(e))
        client_session.cleanup_pasv()
        return

    # 3. Esperar conexión de datos
    try:
        print("Waiting for data connection for file upload...")
        data_conn, data_addr = client_session.data_socket.accept()
        print(f"Data connection established with {data_addr}")

    except socket.error as e:
        print(f"Data connection error: {e}")
        server.send_response(client_socket, 425, "Can't open data connection")
        client_session.cleanup_pasv()
        return

    # 4. Transferencia de archivo (streaming)
    try:
        server.send_response(client_socket, 150, f"Opening data connection for {filename}")

        success, message = store_file_optimized(user_root, client_session.current_directory, filename, data_conn)

        data_conn.close()

        if success:
            server.send_response(client_socket, 226, message)
            print(f"STOR successful: {virtual_path} - {message}")
        else:
            server.send_response(client_socket, 550, message)
            print(f"STOR failed: {message}")

    except Exception as e:
        print(f"Error in STOR command: {e}")
        server.send_response(client_socket, 450, "Requested file action not taken")

    finally:
        client_session.cleanup_pasv()
