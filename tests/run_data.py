# tests/run_data.py
import argparse
import logging
import time

from server.modules.app import DataNode

ROOT_DIRECTORY = "/tmp/ftp_root"

logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, help="ID del DataNode")
    parser.add_argument("--ip", required=True, help="IP del nodo")
    parser.add_argument("--port", type=int, default=9000, help="Puerto interno de escucha")
    parser.add_argument("--data-root", default=ROOT_DIRECTORY, help="Directorio raíz del filesystem")
    parser.add_argument("--discovery-timeout", type=float, default=0.8)
    parser.add_argument("--heartbeat-interval", type=int, default=2)
    args = parser.parse_args()

    node_name = args.id
    ip = args.ip
    port = args.port
    data_root = args.data_root

    print(f"[INFO] Iniciando DataNode '{node_name}' en {ip}:{port}")
    print(f"[INFO] Data root: {data_root}")

    node = DataNode(node_name=node_name,ip=ip,port=port, fs_root= data_root, discovery_timeout=args.discovery_timeout, heartbeat_interval=args.heartbeat_interval)

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print(f"[INFO] DataNode '{node_name}' detenido")

if __name__ == "__main__":
    main()
