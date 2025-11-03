import os
import socket
import random
import ipaddress
import logging

logger = logging.getLogger(__name__)


def handle_pasv(command, client_socket, client_session):
    """Maneja comando PASV - modo pasivo para transferencia de datos.

    - usa el rango PASV_MIN_PORT..PASV_MAX_PORT (env) para elegir puerto
    - bind a 0.0.0.0 para aceptar conexiones desde dentro y desde fuera
    - anuncia PASV_ADVERTISE_HOST (env) para clientes externos; si el
      cliente parece estar dentro del overlay (OVERLAY_SUBNET env) anuncia
      la IP local del contenedor
    - guarda el socket/puerto en la sesión con `set_pasv` """
    
    if not client_session.is_authenticated():
        client_session.send_response(client_socket, 530, "Not logged in")
        return

    if not command.require_args(0):
        client_session.send_response(client_socket, 501, "Syntax error in parameters")
        return

    # limpiar estado PASV previo
    try:
        client_session.cleanup_pasv()
    except Exception:
        pass

    try:
        # crear socket pasivo en rango configurado
        port_min = int(os.getenv('PASV_MIN_PORT', '30000'))
        port_max = int(os.getenv('PASV_MAX_PORT', '30100'))
        data_socket, data_port = create_data_socket(port_min, port_max)

        # Guardar en la sesión
        client_session.set_pasv(data_socket, data_port)
        
        # decidir IP a anunciar según origen del cliente
        client_ip = None
        try:
            client_ip = client_session.client_address[0]
        except Exception:
            try:
                client_ip = client_socket.getpeername()[0]
            except Exception:
                client_ip = None

        pasv_ip = get_pasv_ip(client_ip)

        try:
            pasv_ip = socket.gethostbyname(pasv_ip)
        except Exception:
            # fallback a localhost
            pasv_ip = '127.0.0.1'

        ip_parts = pasv_ip.split('.')
        port_high = data_port // 256
        port_low = data_port % 256
        pasv_response = f"Entering Passive Mode ({','.join(ip_parts)},{port_high},{port_low})"

        client_session.send_response(client_socket, 227, pasv_response)

    except Exception as e:
        client_session.send_response(client_socket, 425, "Can't open data connection")
        

def create_data_socket(port_min=30000, port_max=30100):
    """Crea y configura un socket TCP para modo pasivo y devuelve (socket, puerto)."""

    for _ in range(50):

        data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        port = random.randint(port_min, port_max)

        try:
            data_socket.bind(('0.0.0.0', port))
            data_socket.listen(1)
            return data_socket, port
        
        except OSError:
            try:
                data_socket.close()
            except Exception:
                pass
            continue

    raise RuntimeError("No free PASV port in configured range")

def get_pasv_ip(client_ip: str) -> str:
    """
    Determina qué IP anunciar al cliente según su ubicación.
    - Si el cliente pertenece al rango de red privada Docker → usar IP interna del contenedor.
    - Si no, usar la IP pública pasada por variable de entorno.
    """
    overlay_range = os.getenv("OVERLAY_SUBNET", "10.0.0.0/8")
    advertise = os.getenv("PASV_ADVERTISE_HOST")  # host/IP announced to external clients

    # si no conocemos el client_ip, devolver advertise si existe, si no, usar local host
    if not client_ip:
        return advertise or socket.gethostbyname(socket.gethostname())

    try:
        client = ipaddress.ip_address(client_ip)
    except Exception:
        # Malformed client IP; fallback
        return advertise or socket.gethostbyname(socket.gethostname())

    try:
        overlay_net = ipaddress.ip_network(overlay_range, strict=False)
    except Exception:
        overlay_net = None

    # Si el cliente está en la red overlay configurada, usamos la IP local del contenedor
    if overlay_net and client in overlay_net:
        try:
            pasv_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            pasv_ip = '127.0.0.1'
        logger.info("[PASV] client %s detected as INTERNAL; announcing %s", client_ip, pasv_ip)
        return pasv_ip

    # Cliente externo: anunciar lo que venga de la config de entorno; si no está, intentar local
    if advertise:
        logger.info("[PASV] client %s detected as EXTERNAL; announcing %s", client_ip, advertise)
        return advertise

    try:
        fallback = socket.gethostbyname(socket.gethostname())
    except Exception:
        fallback = '127.0.0.1'
    logger.info("[PASV] client %s detected as EXTERNAL (no advertise); announcing %s", client_ip, fallback)
    return fallback
