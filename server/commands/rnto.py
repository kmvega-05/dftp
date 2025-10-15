from entities.file_system_manager import rename_path, get_user_root_directory, secure_path_resolution

def handle_rnto(command, client_socket, server, client_session):
    """Maneja comando RNTO - Rename To (rename target path)."""
    # 1. Autenticación
    if not client_session.is_authenticated():
        server.send_response(client_socket, 530, "Not logged in")
        return

    # 2. Validar argumentos
    if not command.require_args(1):
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return

    # 3. Verificar que se haya ejecutado RNFR previamente
    old_virtual_path = client_session.get_rename_from()
    if not old_virtual_path:
        server.send_response(client_socket, 503, "RNFR required first")
        return

    # 4. Obtener el nuevo path dado por el usuario
    requested_new_path = command.get_arg(0)
    user_root = get_user_root_directory(client_session.username)

    try:
        # RNTO puede recibir ruta absoluta o relativa → siempre resolvemos con secure_path_resolution
        new_virtual_path = secure_path_resolution(user_root, client_session.current_directory, requested_new_path)

    except ValueError as e:
        # Si secure_path_resolution detecta traversal o ruta inválida
        server.send_response(client_socket, 550, str(e))
        client_session.clear_rename_from()
        return

    print(f"Old : {old_virtual_path}, New: {new_virtual_path}")

    # 5. Renombrar el archivo o directorio
    success, message = rename_path(user_root, client_session.current_directory, old_virtual_path, new_virtual_path)

    # 6. Enviar respuesta
    if success:
        server.send_response(client_socket, 250, message)
        print(f"RNTO successful: {old_virtual_path} -> {new_virtual_path}")
    else:
        server.send_response(client_socket, 550, message)
        print(f"RNTO failed: {message}")

    # 7. Limpiar estado RNFR
    client_session.clear_rename_from()
