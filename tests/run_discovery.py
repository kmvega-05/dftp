import argparse
import logging
import socket

from server.modules.discovery import DiscoveryNode

logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, help="ID del DiscoveryNode")
    parser.add_argument("--ip", required=False, help="IP del nodo (opcional). Si no se pasa, se resolverá por DNS usando el nombre del nodo en Docker/Swarm")
    parser.add_argument("--port", type=int, default=9000, help="Puerto de escucha")
    parser.add_argument("--discovery-interval", type=int, default=5)
    parser.add_argument("--discovery-timeout", type=float, default=0.8)
    parser.add_argument("--heartbeat-timeout", type=int, default=10)
    parser.add_argument("--clean-interval", type=int, default=10)
    args = parser.parse_args()

    if not args.ip:
        try:
            args.ip = socket.gethostbyname(args.id)
            print(f"[INFO] Resolved IP via DNS for {args.id}: {args.ip}")
        except Exception:
            args.ip = "127.0.0.1"
            print(f"[WARNING] Could not resolve {args.id} via DNS, falling back to {args.ip}")

    node = DiscoveryNode(node_name=args.id, ip=args.ip, port=args.port, discovery_interval=args.discovery_interval, discovery_timeout=args.discovery_timeout, heartbeat_timeout=args.heartbeat_timeout, clean_interval=args.clean_interval)

    try:
        while True:
            import time
            time.sleep(1)

    except KeyboardInterrupt:
        print(f"[INFO] DiscoveryNode '{args.id}' detenido")

if __name__ == "__main__":
    main()
