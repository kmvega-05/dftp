import socket
import threading
import logging
from server.modules.comm.message import Message

logger = logging.getLogger("dftp.comm.tcp_server")

class TCPServer:
    def __init__(self, ip: str, port: int, on_message):
        """
        Params:
            - ip: dirección del servidor
            - port: puerto del servidor
            - on_message: callback que recibe Message y socket cliente
                debe devolver un objeto Message como respuesta, o None
        """
        self.ip = ip
        self.port = port
        self.on_message = on_message
        self.running = False
        self.server_thread = None
        self.listen_socket = None

    # ---------------- Métodos públicos ----------------
    def start(self):
        """Inicia el servidor en un hilo independiente."""
        self._create_socket()
        self.running = True
        self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self.server_thread.start()

    def stop(self):
        """Detiene el servidor y cierra conexiones."""
        self.running = False
        if self.listen_socket:
            try:
                self.listen_socket.close()
            except Exception:
                logger.exception("Error cerrando socket de escucha")
        logger.info("TCPServer detenido")

    # ---------------- Métodos internos ----------------
    def _create_socket(self):
        """Crea y configura el socket de escucha."""
        self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listen_socket.bind((self.ip, self.port))
        self.listen_socket.listen(5)
        self.listen_socket.settimeout(0.5) 

    def _server_loop(self):
        """ Bucle que se mantiene a la espera de nuevas conexiones """
        logger.debug("Entrando a server_loop")
        while self.running:
            try:
                client_sock, addr = self.listen_socket.accept()

            except socket.timeout:
                continue

            except Exception:
                logger.exception("Error en accept()")
                continue
            
            logger.debug("Conexión aceptada: %s", addr)
            t = threading.Thread(target=self._handle_client, args=(client_sock, addr), daemon=True)

            t.start()
        logger.debug("Salió del server_loop")

    def _handle_client(self, client_sock, addr):
        """Hilo que se encarga de atender/manejar a cada cliente."""

        logger.debug("Hilo de cliente iniciado: %s", addr)

        buffer = b""
        client_sock.settimeout(0.5)

        try:
            while self.running:
                try:
                    # Recibir datos por parte del cliente
                    data = client_sock.recv(1024)

                except socket.timeout:
                    continue

                except Exception:
                    logger.exception("Error en recv()")
                    break
                
                # Si no se reciben más datos cerrar la conexión.
                if not data:
                    logger.debug("recv() devolvió 0 bytes, desconectando %s", addr)
                    break

                logger.debug("Datos recibidos de %s: %d bytes", addr, len(data))
                buffer += data

                # Procesar todas las líneas completas en el buffer 
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    try:
                        # Parsear mensaje
                        msg = Message.from_json(line.decode())
                        
                        # Procesar mensaje usando on_message
                        response = self.on_message(msg)

                        # Enviar respuesta si existe
                        if response:
                            logger.debug("Enviando respuesta a %s: %s", addr, response.header.get("type"))
                            client_sock.sendall(response.to_json().encode())

                    except Exception:
                        logger.exception("Error procesando mensaje de %s", addr)
        finally:
            try:
                client_sock.close()

            except Exception:
                logger.exception("Error cerrando socket cliente %s", addr)

            logger.debug("Cliente %s desconectado", addr)
