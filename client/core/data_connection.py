import socket
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class DataConnectionManager:
    def __init__(self, ip: str, port: int):
        """
        Maneja la conexión de datos PASV del cliente FTP.
        """
        self.ip = ip
        self.port = port
        self.data_socket: Optional[socket.socket] = None

    def connect(self):
        """
        Establece la conexión TCP con el servidor en el canal de datos.
        """
        logger.debug(f"Data connection: connecting to {self.ip}:{self.port}")
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_socket.connect((self.ip, self.port))
        logger.debug(f"✓ Data connection established with {self.ip}:{self.port}")
        print(f"[DATA] Connected to {self.ip}:{self.port}")

    def close(self):
        """
        Cierra la conexión de datos.
        """
        if self.data_socket:
            self.data_socket.close()
            logger.debug(f"Data connection closed with {self.ip}:{self.port}")
            self.data_socket = None
            print(f"[DATA] Disconnected from {self.ip}:{self.port}")
    
    def receive_list(self) -> str:
        """
        Recibe la lista de archivos/directorios del servidor.
        """
        logger.debug(f"Receiving listing from {self.ip}:{self.port}")
        buffer = []
        while True:
            data = self.data_socket.recv(4096)
            if not data:
                break
            buffer.append(data.decode('utf-8'))
        result = ''.join(buffer)
        logger.debug(f"Listing received: {len(result)} bytes, {len(result.splitlines())} lines")
        return result
    
    def receive_file(self, local_path: str):
        """
        Recibe un archivo del servidor y lo guarda en local_path.
        """
        logger.debug(f"Receiving file to {local_path}")
        bytes_received = 0
        with open(local_path, 'wb') as f:
            while True:
                data = self.data_socket.recv(4096)
                if not data:
                    break
                f.write(data)
                bytes_received += len(data)
        logger.debug(f"✓ File received: {local_path} ({bytes_received} bytes)")
        print(f"[DATA] File downloaded to {local_path}")

    def send_file(self, local_path: str):
        """
        Envía un archivo al servidor.
        """
        logger.debug(f"Sending file from {local_path}")
        bytes_sent = 0
        with open(local_path, 'rb') as f:
            while chunk := f.read(4096):
                self.data_socket.sendall(chunk)
                bytes_sent += len(chunk)
        logger.debug(f"✓ File sent: {local_path} ({bytes_sent} bytes)")
        print(f"[DATA] File uploaded from {local_path}")
