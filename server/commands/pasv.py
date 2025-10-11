import socket
import random

def handle_pasv(command, client_socket, server, client_session):
    """Maneja comando PASV - modo pasivo para transferencia de datos"""
    if not command.require_args(0):
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return

    # Limpiar cualquier estado PASV previo
    client_session.cleanup_pasv()

    try:
        # Crear socket para datos
        data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Enlazar a un puerto aleatorio (rango 30000-50000)
        data_port = random.randint(30000, 50000)
        data_socket.bind(('0.0.0.0', data_port))
        data_socket.listen(1)
        
        # Guardar en sesión
        client_session.data_socket = data_socket
        client_session.data_port = data_port
        client_session.pasv_mode = True
        
        # Obtener IP local (simplificado - normalmente la IP del servidor)
        ip_parts = ['127', '0', '0', '1']
        port_high = data_port // 256
        port_low = data_port % 256
        
        # Formato FTP: 127,0,0,1,port_high,port_low
        pasv_response = f"Entering Passive Mode ({','.join(ip_parts)},{port_high},{port_low})"
        server.send_response(client_socket, 227, pasv_response)
        
        print(f"PASV mode activated on port {data_port}")
        
    except Exception as e:
        print(f"Error setting up PASV mode: {e}")
        server.send_response(client_socket, 425, "Can't open data connection")
        client_session.cleanup_pasv()