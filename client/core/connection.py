import socket
import logging

logger = logging.getLogger(__name__)

class ControlConnectionManager:
    # TODO: Crear signals para la interfaz grafica
    def __init__(self, host: str, port: int, timeout: float = 10.0):
        self.host = host
        self.port = port 
        self.socket: socket.socket = None 
        self.timeout = timeout

    def connect(self):
        if self.socket is not None:
            raise RuntimeError("Connection already established.")
        try:
            logger.info(f"Connecting to {self.host}:{self.port} (timeout={self.timeout}s)")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
            logger.info(f"✓ Connected to {self.host}:{self.port}")
            print(f"Connected to {self.host}:{self.port}")
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            logger.error(f"✗ Failed to connect to {self.host}:{self.port} - {e}")
            self.socket = None
            raise ConnectionError(f"Failed to connect to {self.host}:{self.port} - {e}")
    
    def disconnect(self):
        if self.socket:
            try:
                logger.info(f"Closing connection to {self.host}:{self.port}")
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()
            logger.info(f"✓ Disconnected from {self.host}:{self.port}")
            print(f"Disconnected from {self.host}:{self.port}")
        self.socket = None
    
    def send_command(self, command: str):
        if self.socket is None:
            raise RuntimeError("No connection established.")
        if not command.endswith('\r\n'):
            command += '\r\n'
        logger.debug(f"→ SEND: {command.strip()}")
        self.socket.sendall(command.encode('utf-8'))
        print(f"Sent command: {command}")
    
    def receive_response(self) -> str:
        if self.socket is None:
            raise RuntimeError("No connection established.")
        chunks = []
        while True:
            try:
                data = self.socket.recv(4096)
                if not data:
                    break
                chunks.append(data.decode('utf-8'))
                if len(data) < 4096:
                    break
            except socket.timeout:
                break
        response = ''.join(chunks).strip()
        
        # Clean up server echo/debug prefix (e.g., "> " or ">>")
        # Some servers echo the response with a prefix
        while response.startswith('>') or response.startswith('*'):
            response = response[1:].strip()
        
        logger.debug(f"← RECV: {response}")
        print(f"Received response: {response}")
        return response