import json
import time
import uuid

class Message:
    """
    Representa un mensaje del protocolo de comunicación entre nodos.

    Estructura:
        - header: dict
            Contiene información de enrutamiento y tipo de mensaje.
            Campos:
                * type (str): Tipo del mensaje, por ejemplo "DISCOVERY_REGISTER".
                * src (str): IP del nodo que envía el mensaje.
                * dst (str): IP del nodo destino.
        - payload: dict
            Contiene los datos específicos que se quieren transmitir.
            Puede variar según el tipo de mensaje.
        - metadata: dict
            Contiene información adicional para control y seguimiento.
            Siempre incluye:
                * msg_id (str): Identificador único del mensaje.
                * timestamp (int): Marca de tiempo UNIX al momento de creación.
            Puede contener otros campos opcionales.

    Interfaz pública:
        - to_json() -> str
            Serializa el mensaje a JSON terminado en '\n', listo para enviar por TCP.
        - from_json(raw: str) -> Message
            Deserializa un JSON recibido y devuelve un objeto Message.
        - __repr__() -> str
            Representación legible para debug."""
    
    def __init__(self, type: str, src: str, dst: str, payload: dict = None, metadata: dict = None):
        
        self.header = {"type": type, "src": src, "dst": dst }
        self.payload = payload or {}
        default_metadata = {"msg_id": str(uuid.uuid4()), "timestamp": int(time.time())}

        if metadata:
            default_metadata.update(metadata) 

        self.metadata = default_metadata

    def to_json(self) -> str:
        """
        Serializa el mensaje a JSON terminado en '\n', listo para enviar por TCP.
        """
        return json.dumps({
            "header": self.header,
            "payload": self.payload,
            "metadata": self.metadata
        }) + "\n"

    @staticmethod
    def from_json(raw: str) -> "Message":
        """
        Deserializa un JSON recibido y devuelve un objeto Mensaje.
        """
        data = json.loads(raw)
        return Message(
            type=data["header"]["type"],
            src=data["header"]["src"],
            dst=data["header"].get("dst"),
            payload=data.get("payload"),
            metadata=data.get("metadata")
        )

    def __repr__(self):
        return f"Mensaje(type={self.header['type']}, src={self.header['src']}, dst={self.header.get('dst')}, payload={self.payload})"
