import time
from enum import Enum

class NodeType(Enum):
    ROUTING = "ROUTING"
    PROCESSING = "PROCESSING"
    DATA = "DATA"
    AUTH = "AUTH"
    DISCOVERY = "DISCOVERY"

class ServiceRegister:
    """
    Representa un nodo registrado en el DiscoveryNode.
    
    .Campos:
        . name : identificador único del nodo.
        . ip   : dirección ip del nodo
        . node_role : rol del nodo
        . last_heartbeat : última señal enviada por el nodo

    """
    def __init__(self, name: str, ip: str, node_role: NodeType):
        self.name = name
        self.ip = ip
        self.node_role = node_role
        self.last_heartbeat = time.time()

    def heartbeat(self, ip):
        """
        Actualiza el timestamp del último heartbeat recibido.
        """
        self.ip = ip
        self.last_heartbeat = time.time()

    def to_dict(self) -> dict:
        """
        Devuelve una representación serializable del nodo.
        """
        return {
            "name": self.name,
            "ip": self.ip,
            "role": self.node_role.value,
            "last_heartbeat": self.last_heartbeat
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ServiceRegister':
        service_register = cls(name=data["name"], ip=data["ip"], node_role = NodeType(data["role"]))
        return service_register

    def __str__(self):
        return f"{self.name} ({self.node_role.value}) - {self.ip}"

    def __eq__(self, other):
        if not isinstance(other, ServiceRegister):
            return False
        return self.ip == other.ip and self.name == other.name

    def __hash__(self):
        return hash((self.name, self.ip))
