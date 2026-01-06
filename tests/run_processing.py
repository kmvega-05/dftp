import argparse
import logging
import socket
from server.modules.app import ProcessingNode

logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, help="ID del ProcessingNode")
    parser.add_argument("--ip", required=False, help="IP del nodo (opcional). Si no se pasa, se resolverá por DNS usando el nombre del nodo en Docker/Swarm")
    parser.add_argument("--port", type=int, default=9000, help="Puerto interno de escucha")
    parser.add_argument("--discovery-timeout", type=float, default=0.8)
    parser.add_argument("--heartbeat-interval", type=int, default=2)
    args = parser.parse_args()

    if not args.ip:
        try:
            args.ip = socket.gethostbyname(args.id)
            print(f"[INFO] Resolved IP via DNS for {args.id}: {args.ip}")
            
        except Exception:
            args.ip = "127.0.0.1"
            print(f"[WARNING] Could not resolve {args.id} via DNS, falling back to {args.ip}")


    node = ProcessingNode(node_name=args.id, ip=args.ip, internal_port=args.port, discovery_timeout=args.discovery_timeout, heartbeat_interval=args.heartbeat_interval)

    try:
        while True:
            import time
            time.sleep(1)

    except KeyboardInterrupt:
        print(f"[INFO] ProcessingNode '{args.id}' detenido")

if __name__ == "__main__":
    main()
