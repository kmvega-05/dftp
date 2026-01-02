import logging
import socket
from server.modules.comm.communication_node.tcp_protocol import TCPServer, TCPClient
from server.modules.comm.message import Message

logger = logging.getLogger("dftp.comm.communication_node")

class CommunicationNode:
    """
    Nodo base para todos los nodos del sistema, encargado del intercambio de mensajes discretos
    entre nodos mediante TCP y del envío/recepción de streams de bytes.  

    Proporciona soporte para:
        - Comunicación síncrona (espera de respuesta)
        - Comunicación asíncrona (fire-and-forget)
        - Transmisión de streams de bytes para operaciones tipo FTP (RETR/STOR/LIST)

    Campos principales:
        - node_name (str): Identificador del nodo.
        - ip (str): IP donde escucha el nodo.
        - port (int): Puerto donde escucha el nodo.
        - handlers (Dict[str, Callable[[Message], Optional[Message]]]): Diccionario de handlers
          por tipo de mensaje. Cada callback recibe (Message) y retorna un Message o None.
        - server (TCPServer): Servidor TCP interno que recibe mensajes discretos.
        - client (TCPClient): Cliente TCP para enviar mensajes discretos a otros nodos.

    Métodos públicos:
        - stop_server() -> None
            Detiene el servidor TCP que recibe mensajes.
        - register_handler(msg_type: str, callback: Callable[[Message], Optional[Message]]) -> None
            Registra un callback para un tipo de mensaje específico.
        - send_message(ip: str, port: int, msg: Message, await_response: bool = True, timeout: float = 1.0) -> Optional[Message]
            Envía un mensaje discreto a un nodo destino.
            - await_response=True: espera la respuesta y la retorna.
            - await_response=False: envía el mensaje y retorna None.
        - send_stream(dst_ip: str, dst_port: int, data_iterable, chunk_size: int = 4096) -> None
            Envía un stream de bytes a un nodo destino mediante un socket TCP.
        - recv_stream(listen_ip: str, listen_port: int, chunk_size: int = 4096) -> Iterator[bytes]
            Escucha en un puerto TCP y devuelve un iterable de chunks de bytes recibidos.
    """

    def __init__(self, node_name: str, ip: str, port: int):
        self.node_name = node_name
        self.ip = ip
        self.port = port
        self.handlers = {} 

        # Instancia TCPServer y TCPClient
        self.server = TCPServer(ip, port, self._on_message)
        self.client = TCPClient()

        # Iniciar el servidor TCP
        self._start_server()

    # ---------------- Métodos Internos ----------------
    def _start_server(self):
        """Inicia el servidor TCP para recibir mensajes."""
        self.server.start()

    def _on_message(self, message: Message):
        """Se llama automáticamente al recibir un mensaje.
         . Busca el handler registrado para el tipo de mensaje.
         . Si existe, lo ejecuta y retorna la respuesta.
         . Si no existe, retorna None.
        """
        handler = self.handlers.get(message.header['type'])
        if handler:
            response = handler(message)
            return response
        else:
            logger.debug("No hay handler para tipo '%s'", message.header['type'])
            return None
        
    # --------------- Métodos Públicos --------------------------
    def stop_server(self):
        """Detiene el servidor TCP."""
        self.server.stop()
        logger.info("Server stopped on %s:%s", self.ip, self.port)

    def register_handler(self, msg_type: str, callback):
        """
        .Registra un callback para un tipo de mensaje específico.
         Params:
            - callback: función que recibe (Message) y devuelve Message o None
            (Se llama automáticamente al recibir un mensaje de ese tipo.)
        """
        self.handlers[msg_type] = callback
        logger.debug("Handler registrado para tipo '%s' en nodo %s", msg_type, self.node_name)


    def send_message(self, ip, port, msg, await_response=True, timeout=1.0):
        """ Envía un mensaje a un nodo destino.
          Params:
            - ip: dirección del nodo destino
            - msg: instancia de Message a enviar
            - await_response: si es True, espera y retorna la respuesta del nodo destino
            - timeout: tiempo máximo para conectar y recibir respuesta
        """
        
        logger.debug("Enviando mensaje a %s:%s tipo=%s src=%s dst=%s", ip, port, msg.header.get("type"), msg.header.get("src"), msg.header.get("dst"))
        
        response = self.client.send_message(ip, port, msg, await_response, timeout=timeout)
        
        logger.debug("Respuesta recibida de %s:%s -> %s", ip, port, getattr(response, "header", None))
        
        return response
    
    def send_stream(dst_ip: str, dst_port: int, data_iterable, chunk_size=4096):
        """
        Envía un stream de bytes a un nodo destino.

        Params:
            dst_ip: IP del destino
            dst_port: puerto TCP del canal de datos
            data_iterable: iterable de bytes o un objeto file-like
            chunk_size: tamaño de cada bloque enviado
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:

            sock.connect((dst_ip, dst_port))
            for chunk in data_iterable:
                sock.sendall(chunk)

        finally:
            if sock:
                sock.close()

    def recv_stream(listen_ip: str, listen_port: int, chunk_size=4096):
        """Recibe un stream de bytes y lo devuelve como iterable de chunks."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((listen_ip, listen_port))
        sock.listen(1)
        conn, _ = sock.accept()
        
        try:
            while True:
                chunk = conn.recv(chunk_size)
                if not chunk:
                    break
                yield chunk

        finally:
            if conn:
                conn.close()

            if sock:
                sock.close()  
