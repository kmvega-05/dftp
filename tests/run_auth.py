import argparse
import logging

from server.modules.app import AuthNode

logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, help="ID del AuthNode (usar _ en lugar de -)")
    parser.add_argument("--ip", required=True, help="IP del nodo")
    parser.add_argument("--port", type=int, default=9000, help="Puerto de escucha")
    parser.add_argument("--discovery-timeout", type=float, default=0.8, help="Timeout de discovery")
    parser.add_argument("--heartbeat-interval", type=int, default=2, help="Intervalo de heartbeat")
    args = parser.parse_args()

    node_name = args.id
    ip = args.ip
    port = args.port

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
