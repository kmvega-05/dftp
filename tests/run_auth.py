import argparse
import logging
import socket
import os
from server.modules.app import AuthNode

logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, help="ID del AuthNode (usar _ en lugar de -)")
    parser.add_argument("--ip", required=False, help="IP del nodo (opcional). Si no se pasa, se resolverá por DNS usando el nombre del nodo en Docker/Swarm")
    parser.add_argument("--port", type=int, default=9000, help="Puerto de escucha")
    parser.add_argument("--discovery-timeout", type=float, default=0.8, help="Timeout de discovery")
    parser.add_argument("--heartbeat-interval", type=int, default=2, help="Intervalo de heartbeat")
    parser.add_argument("--subnet", default=None, help='Subnet del sistema')
    args = parser.parse_args()

    node_name = args.id
    ip = args.ip
    port = args.port

    if not ip:
        try:
            ip = socket.gethostbyname(node_name)
            print(f"[INFO] Resolved IP via DNS for {node_name}: {ip}")
        except Exception:
            ip = "127.0.0.1"
            print(f"[WARNING] Could not resolve {node_name} via DNS, falling back to {ip}")


    if args.subnet:
        os.environ['DFTP_SUBNET'] = args.subnet

    print(f"[INFO] Iniciando AuthNode '{node_name}' en {ip}:{port}")

    node = AuthNode(node_name=node_name, ip=ip, port=port, discovery_timeout=args.discovery_timeout, heartbeat_interval=args.heartbeat_interval)
    
    # Mantener el nodo corriendo
    try:
        while True:
            import time
            time.sleep(1)

    except KeyboardInterrupt:
        print(f"[INFO] AuthNode '{node_name}' detenido")

if __name__ == "__main__":
    main()
