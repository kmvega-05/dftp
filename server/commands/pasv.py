import os
import socket
import random
import ipaddress


def handle_pasv(command, client_socket, server, client_session):
    """Maneja comando PASV - modo pasivo para transferencia de datos"""
    if not command.require_args(0):
        server.send_response(client_socket, 501, "Syntax error in parameters")
        return
    
    # Limpiar estado PASV previo si existe
    client_session.cleanup_pasv()

    try:
        # Crear socket pasivo
        data_socket, data_port = create_data_socket()

        # Actualizar session
        client_session.data_socket = data_socket
        client_session.data_port = data_port
        client_session.pasv_mode = True

        # Determinar IP adecuada para el cliente
        client_ip = client_session.client_address[0]
        pasv_ip = get_pasv_ip(client_ip)

        # Construir respuesta FTP
        ip_parts = pasv_ip.split('.')
        port_high = data_port // 256
        port_low = data_port % 256
        pasv_response = f"Entering Passive Mode ({','.join(ip_parts)},{port_high},{port_low})"

        # Enviar respuesta al cliente
        server.send_response(client_socket, 227, pasv_response)
        print(f"[PASV] Modo pasivo activado en {pasv_ip}:{data_port}")

    except Exception as e:
        print(f"[PASV] Error configurando modo pasivo: {e}")
        server.send_response(client_socket, 425, "Can't open data connection")
        client_session.cleanup_pasv()


def create_data_socket(port_min=50000, port_max=50010):
    """
    Crea y configura un socket TCP para modo pasivo.
    Retorna (socket, puerto_asignado).
    """
    data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    for _ in range(10):
        port = random.randint(port_min, port_max)
        try:
            data_socket.bind(('0.0.0.0', port))
            data_socket.listen(1)
            print(f"[PASV] Socket de datos escuchando en 0.0.0.0:{port}")
            return data_socket, port
        except OSError:
            continue

    raise RuntimeError("No se pudo encontrar un puerto libre para modo PASV")

def get_pasv_ip(client_ip: str) -> str:
    """
    Determina qué IP anunciar al cliente según su ubicación.
    - Si el cliente pertenece al rango de red privada Docker → usar IP interna del contenedor.
    - Si no, usar la IP pública pasada por variable de entorno.
    """
    overlay_range = os.getenv("OVERLAY_SUBNET", "10.0.0.0/24")
    public_ip = os.getenv("PUBLIC_IP")

    client = ipaddress.ip_address(client_ip)
    overlay_net = ipaddress.ip_network(overlay_range, strict=False)

    if client in overlay_net:
        # Cliente interno → usar IP interna del contenedor
        pasv_ip = socket.gethostbyname(socket.gethostname())
        print(f"[PASV] Cliente interno detectado ({client_ip}), usando IP interna {pasv_ip}")
    else:
        # Cliente externo → usar IP pública
        if not public_ip:
            raise RuntimeError("PUBLIC_IP no configurada para clientes externos")
        pasv_ip = public_ip
        print(f"[PASV] Cliente externo detectado ({client_ip}), usando IP pública {pasv_ip}")

    return pasv_ip
