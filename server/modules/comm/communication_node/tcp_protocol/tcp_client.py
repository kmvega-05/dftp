import socket
import logging
from server.modules.comm.message import Message

logger = logging.getLogger("dftp.comm.tcp_client")

class TCPClient:

    def send_message(self, dst_ip: str, dst_port: int, message: Message, await_response: bool = True, timeout: float = 1.0):
        """
        Envía un Message a un nodo destino.
         Params:
            - dst_ip: dirección IP del nodo destino
            - dst_port: puerto del nodo destino
            - message: instancia de Message a enviar
            - await_response: si es True, espera y retorna la respuesta del nodo destino
            - timeout: tiempo máximo para conectar y recibir respuesta
        """
        sock = None
        try:
            sock = self._connect(dst_ip, dst_port, timeout)

            if sock is None:
                return None
            
            self._send_raw(sock, message)

            if await_response:
                response = self._recv_response(sock, timeout)
                return response
            
            return None
        
        finally:
            if sock is not None:

                try:
                    sock.close()

                except Exception:
                    logger.exception("Error cerrando socket")

    # ---------------- Métodos internos ----------------
    def _connect(self, ip: str, port: int, timeout: float):
        """Crea y conecta un socket TCP al destino con timeout."""
        sock = None

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((ip, port))

        except Exception:
            if sock:
                try:
                    sock.close()

                except Exception:
                    pass

            return None
        
        return sock

    def _send_raw(self, sock: socket.socket, message: Message):
        """Envía el mensaje serializado por TCP."""
        data = message.to_json().encode()
        try:
            sock.sendall(data)

        except Exception:
            logger.exception("Error enviando mensaje a %s", message.header.get("dst"))

    def _recv_response(self, sock, timeout: float) -> Message:
        """Recibe un Message de respuesta del servidor con timeout."""
        sock.settimeout(timeout)
        buffer = ""
        while True:
            try:
                data = sock.recv(1024).decode()

            except socket.timeout:
                logger.debug("Timeout esperando respuesta")
                return None
            
            except Exception:
                logger.exception("Error recibiendo respuesta")
                return None
            
            if not data:
                break

            buffer += data
            if "\n" in buffer:
                line, _ = buffer.split("\n", 1)
                try:
                    response = Message.from_json(line)
                    logger.debug("Respuesta recibida de %s: %s", response.header.get("src"), response.header.get("type"))
                    return response
                
                except Exception:
                    logger.exception("Error parseando respuesta")
                    return None
        return None