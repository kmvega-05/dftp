import os
import threading
import time
import ipaddress
import logging
import concurrent.futures

from server.modules.comm import CommunicationNode, Message, MessageType
from server.modules.discovery.discovery_node.entities import NodeType

logger = logging.getLogger("dftp.location.location_node")
DISCOVERY_PORT = 9000

class LocationNode(CommunicationNode):
    """
    Nodo que permite interactuar con Discovery Nodes para encontrar otros nodos en la red.

    Campos:
        . discovery_nodes: dict{name: ip} de discovery nodes detectados.
        . node_role: rol del nodo (NodeType) o None si no aplica.
        . subnet: subred en la que buscar discovery nodes.
        . possible_ips: lista de ips posibles en la subred (excepto la propia ip).

    Parámetros de configuración:
        . discovery_timeout: tiempo que se espera por respuesta de un discovery_node.
        . heartbeat_interval: frecuencia con la que se envían heartbeats a los discovery_nodes.
        . discovery_workers: número de hilos para enviar señales de descubrimiento en paralelo.

    Métodos públicos:
        . get_discovery_node() -> obtiene la dirección ip de un discovery node conocido.
        . query_by_name(name) -> contacta con un discovery node pidiendo la información de un nodo por su nombre.
        . query_by_role(node_role) -> contacta con un discovery node pidiendo la lista de nodos del rol especificado.

    Hilos internos:
        . _send_heartbeat_loop: hilo que envía heartbeats periódicos a todas las IPs de la subred.
          Actualiza discovery_nodes con los Discovery Nodes que respondieron.
    """

    def __init__(self, node_name: str, ip: str, port: int, node_role: NodeType = None, discovery_timeout: float = 0.8,
                 heartbeat_interval: int = 2, discovery_workers: int = 32):
        """Constructor para LocationNode"""

        super().__init__(node_name, ip, port)

        self.discovery_nodes: dict[str, str] = {}
        self.discovery_nodes_lock = threading.Lock()
        self.node_role = node_role

        self.discovery_timeout = discovery_timeout
        self.heartbeat_interval = heartbeat_interval
        self.discovery_workers = discovery_workers

        self.subnet = os.getenv("DFTP_SUBNET")
        if not self.subnet:
            raise ValueError("DFTP_SUBNET no está configurado en LocationNode")
        
        self.possible_ips = self._get_possible_ips()
        self._stop = threading.Event()
        
        logger.info("LocationNode '%s' iniciado en %s:%s (subnet=%s)", self.node_name, self.ip, self.port, self.subnet)
        
        # Iniciar hilo de envío de señales
        self.heartbeat_thread = threading.Thread(target=self._send_heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

    # ----------------- Métodos públicos -------------------
    def query_by_name(self, name: str) -> dict | None:
        """
        Consulta a todos los discovery nodes conocidos sobre un nodo específico por nombre.
        Retorna un diccionario con la información del nodo o None si no se encuentra en ningún discovery node.
        """
        with self.discovery_nodes_lock:
            nodes = list(self.discovery_nodes.values())

        if not nodes:
            return None

        for dest_ip in nodes:
            try:
                msg = Message(type=MessageType.DISCOVERY_QUERY_BY_NAME, src=self.ip, dst=dest_ip, payload={"name": name})
                response = self.send_message(dest_ip, DISCOVERY_PORT, msg, await_response=True)

                if response and response.metadata.get("status") == "OK":
                    return response.payload.get("node")
            except Exception as e:
                logger.debug(f"query_by_name: error consultando {dest_ip}: {str(e)}")
                continue

        return None


    def query_by_role(self, node_role: NodeType) -> list | None:
        """
        Consulta a todos los discovery nodes conocidos sobre los nodos con el rol especificado.
        Retorna la lista de nodos (cada nodo es un dict con 'name' e 'ip') o None si no hay resultados.
        """
        with self.discovery_nodes_lock:
            nodes = list(self.discovery_nodes.values())

        if not nodes:
            return None

        for dest_ip in nodes:
            try:
                msg = Message(type=MessageType.DISCOVERY_QUERY_BY_ROLE, src=self.ip, dst=dest_ip,
                            payload={"role": node_role.value})
                response = self.send_message(dest_ip, DISCOVERY_PORT, msg, await_response=True)

                if response and response.metadata.get("status") == "OK":
                    return response.payload.get("nodes") or None
            except Exception as e:
                logger.debug(f"query_by_role: error consultando {dest_ip}: {str(e)}")
                continue

        return None

    # ----------------- Métodos internos -------------------
    def _get_possible_ips(self) -> list[str]:
        """Obtiene todas las posibles IPs de hosts en la subred, exceptuando la propia."""
        net = ipaddress.ip_network(self.subnet, strict=False)
        return [str(ip) for ip in net.hosts() if str(ip) != self.ip]

    # ----------------- Hilo de Heartbeats -------------------
    def _send_heartbeat_loop(self) -> None:
        """Envia periódicamente heartbeats a todas las IPs de la subred para descubrir Discovery Nodes."""
        logger.info("[%s] Iniciando send_heartbeat_loop", self.node_name)
        
        while not self._stop.is_set():
            try:
                found = self._find_discovery_nodes_in_parallel()
                self._update_discovery_nodes(found)
                time.sleep(self.heartbeat_interval)
            except Exception as e:
                logger.exception(f"Error en send_heartbeat_loop: {str(e)}")
                time.sleep(self.heartbeat_interval)
    
    def _find_discovery_nodes_in_parallel(self) -> dict:
        """Envía heartbeats en paralelo a todas las IPs de la subred y devuelve dict name->ip de nodos que respondieron."""
        max_workers = min(self.discovery_workers, max(1, len(self.possible_ips)))
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(self._probe_heartbeat_ip, ip) for ip in self.possible_ips]
            for fut in concurrent.futures.as_completed(futures):
                try:
                    res = fut.result(timeout=self.discovery_timeout + 0.5)
                except Exception:
                    res = (None, None)
                results.append(res)

        return self._collect_heartbeated_nodes(results)

    def _probe_heartbeat_ip(self, ip_addr: str) -> tuple[str, Message]:
        """Envía un heartbeat a la IP especificada y devuelve (ip, response) o (ip, None)."""
        try:
            payload = {"name": self.node_name}
            if self.node_role:
                payload["role"] = self.node_role.value
            payload["ip"] = self.ip

            msg = Message(type=MessageType.DISCOVERY_HEARTBEAT, src=self.ip, dst=ip_addr, payload=payload)
            resp = self.send_message(ip_addr, DISCOVERY_PORT, msg, await_response=True, timeout=self.discovery_timeout)
            return ip_addr, resp
        except Exception as e:
            logger.debug(f"Error enviando heartbeat a {ip_addr}: {str(e)}")
            return ip_addr, None

    def _collect_heartbeated_nodes(self, results) -> dict:
        """Construye dict name->ip a partir de los resultados de heartbeats."""
        found = {}
        for _, response in results:
            if not response:
                continue
            try:
                if response.metadata.get("status") == "OK":
                    name = response.payload.get("name")
                    ip = response.payload.get("ip")
                    if name and ip:
                        found[name] = ip
            except Exception:
                continue
        return found

    def _update_discovery_nodes(self, found: dict) -> None:
        """Actualiza self.discovery_nodes si hubo cambios."""
        with self.discovery_nodes_lock:
            if set(found.items()) != set(self.discovery_nodes.items()):
                self.discovery_nodes = found
