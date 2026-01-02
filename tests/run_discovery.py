import argparse
import logging

from server.modules.discovery import DiscoveryNode

logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, help="ID del DiscoveryNode")
    parser.add_argument("--ip", required=True, help="IP del nodo")
    parser.add_argument("--port", type=int, default=9000, help="Puerto de escucha")
    parser.add_argument("--discovery-interval", type=int, default=10)
    parser.add_argument("--discovery-timeout", type=float, default=0.8)
    parser.add_argument("--heartbeat-timeout", type=int, default=10)
    parser.add_argument("--clean-interval", type=int, default=60)
    args = parser.parse_args()

    node = DiscoveryNode(node_name=args.id, ip=args.ip, port=args.port, discovery_interval=args.discovery_interval, discovery_timeout=args.discovery_timeout, heartbeat_timeout=args.heartbeat_timeout, clean_interval=args.clean_interval)

    try:
        while True:
            import time
            time.sleep(1)

    except KeyboardInterrupt:
        print(f"[INFO] DiscoveryNode '{args.id}' detenido")

if __name__ == "__main__":
    main()
