import ipaddress
import threading
import time
import concurrent.futures
import os
import logging

from server.modules.discovery.discovery_node.entities import ServiceRegister, NodeType, RegisterTable
from server.modules.comm import Message, MessageType
from server.modules.consistency import GossipNode

logger = logging.getLogger("dftp.app.discovery_node")

class DiscoveryNode(GossipNode):
    """Discovery Node
    Nodo que gestiona una tabla de registros de servicios para que otros nodos puedan encontrarse entre ellos.
    La tabla contiene registros de los nodos del sistema incluyendo: Nombre, Ip, Rol, Last_Heartbeat
    
    - Campos:
        . register_table: tabla de registros de servicios.
        . peers: diccionario {name: ip} de otros discovery nodes detectados.
        . subnet: subred en la que buscar otros discovery nodes.
        . possible_ips: lista de ips posibles en la subred (excepto la propia ip).

    - Parámetros de configuración:
        . heartbeat_timeout: tiempo máximo sin recibir heartbeat antes de considerar un nodo inactivo.
        . clean_interval: frecuencia con la que se limpian los nodos inactivos de la tabla.
        . discovery_interval: frecuencia con la que se escanea la subred en busca de otros discovery nodes.
        . discovery_timeout: tiempo máximo para esperar respuesta de un discovery node.
        . discovery_workers: número de hilos para enviar señales de descubrimiento en paralelo.

    - Consultas Disponibles:
        . DISCOVERY_HEARTBEAT: para registrar/actualizar nodos en la tabla.
        . DISCOVERY_QUERY_BY_NAME: para obtener la ip de un nodo dado su nombre.
        . DISCOVERY_QUERY_BY_ROLE: para obtener la lista de ips de nodos con un rol específico.
        . DISCOVERY_QUERY_ALL: para obtener todos los nodos registrados en la tabla.

    - Hilos Internos:
        . _update_peers: escanea la subred en busca de otros discovery nodes y actualiza self.peers.
        . clean_inactive_register_loop: limpia periódicamente los nodos inactivos de la tabla de registros.

    Para realizar una consulta a un Discovery Node enviar el Message correspondiente.
    """

    def __init__(self, node_name: str, ip: str, port: int, heartbeat_timeout: int = 10, clean_interval: int = 60,
        discovery_interval: int = 10, discovery_timeout: float = 0.8, discovery_workers: int = 32):
        
        # Iniciar CommunicationNode para permitir intercambio de mensajes.
        super().__init__(node_name, ip, port)

        self.node_type = NodeType.DISCOVERY

        # Tabla de servicios registrados
        self.register_table = RegisterTable()

        # Conjunto de discovery Nodes
        self.peers: dict[str, str] = {}
        self.peers_lock = threading.Lock()

        # Configuración de red / scanning
        subnet = os.getenv("DFTP_SUBNET")
        if not subnet:
            raise ValueError("DFTP_SUBNET not set")
        
        self.subnet = subnet
        self.possible_ips = self.get_possible_ips()

        # Parámetros de configuración
        self.discovery_interval = discovery_interval
        self.discovery_timeout = discovery_timeout
        self.discovery_workers = discovery_workers
        self.heartbeat_timeout = heartbeat_timeout
        self.clean_interval = clean_interval

        # Registar funciones para manejar distintos tipos de mensajes recibidos.
        self.register_handlers()

        # Iniciar hilos
        self._stop = threading.Event()
        
        # Hilo de descubrimiento de peers
        t1 = threading.Thread(target=self._update_peers, daemon=True)
        t1.start()

        # Hilo de limpieza de registros
        t2 = threading.Thread(target=self.clean_inactive_register_loop, daemon=True)
        t2.start()

        logger.info("DiscoveryNode %s iniciado en %s:%s (subnet=%s)", self.node_name, self.ip, self.port, self.subnet)

    # ---------------- Helpers publicos ----------------
    def register_handlers(self):
        """Registra las funciones para manejar los distintos tipos de mensajes recibidos por el protocolo
        de Comunicación. Las funciones se llamarán automáticamente al recibir un mensaje."""

        self.register_handler(MessageType.DISCOVERY_HEARTBEAT, self._handle_heartbeat)
        self.register_handler(MessageType.DISCOVERY_QUERY_BY_NAME, self._handle_query_by_name)
        self.register_handler(MessageType.DISCOVERY_QUERY_BY_ROLE, self._handle_query_by_role)
        self.register_handler(MessageType.DISCOVERY_QUERY_ALL, self._handle_query_all)

    def get_possible_ips(self) -> list[str]:
        """Obtiene todas las posibles ips de hosts de la red exceptuando la ip propia para 
        el envío de mensajes"""
        net = ipaddress.ip_network(self.subnet, strict=False)
        return [str(ip) for ip in net.hosts() if str(ip) != self.ip]

    # ---------------- Handlers obligatorios ----------------
    def _handle_heartbeat(self, message: Message):
        """Maneja DISCOVERY_HEARTBEAT:
            . Registra/actualiza registro de un nodo del sistema
            . Retorna información de contacto del nodo actual para que otros nodos puedan intercambiar mensajes
            . Usado para descubrimiento por parte de otros nodos(incluidos otros Discovery Nodes)

        Recibe Message(... payload: { name, ip, role })
        Retorna Message(.. payload: { ip, name}) -> del nodo actual
        """
        try:
            payload = message.payload or {}

            # Obtener información recibida en el mensaje
            name = payload.get("name")
            ip = payload.get("ip")
            role = payload.get("role")

            # Manejar mensaje incorrecto
            if not name or not ip or not role:
                return Message(type=MessageType.DISCOVERY_HEARTBEAT_ACK, src=self.ip, dst=message.header.get("src"), payload={}, metadata= {"status": "ERROR", "error_msg": "Missing fields"})

            # Obtener rol del nodo
            try:
                node_role = NodeType(role)

            except Exception:
                return Message(type=MessageType.DISCOVERY_HEARTBEAT_ACK, src=self.ip, dst=message.header.get("src"), payload={}, metadata = {"status": "ERROR", "error_msg": "Invalid role"})

            # Si quien envía es un discovery node (role == 'DISCOVERY') lo tratamos como peer
            if node_role == NodeType.DISCOVERY:
                return Message(type=MessageType.DISCOVERY_HEARTBEAT_ACK, src=self.ip, dst=message.header.get("src"), payload={"ip": self.ip, "name": self.node_name}, metadata = {"status": "OK"})

            # Sino buscar nodo en la tabla
            existing = self.register_table.get_node(name)
            
            # Si el nodo ya estaba registrado, actualizar ip y heartbeat
            if existing:
                existing.heartbeat(ip)
                
                with self.merging_lock:
                    for peer_ip in self.peers.values():
                        repl_msg = Message(MessageType.GOSSIP_UPDATE, self.ip, peer_ip, payload={"op": "add", "registry" : existing.to_dict()})
                        self.send_message(peer_ip, 9000, repl_msg, await_response=False)

            # Si no, registrarlo
            else:
                try:
                    sr = ServiceRegister(name, ip, node_role)
                    self.register_table.add_node(sr)
                    logger.info(f"New node registered: {name}, {str(node_role)} : ({ip})")
                    
                    with self.merging_lock:
                        for peer_ip in self.peers.values():
                            repl_msg = Message(MessageType.GOSSIP_UPDATE, self.ip, peer_ip, payload={"op": "add", "registry" : sr.to_dict()})
                            self.send_message(peer_ip, 9000, repl_msg, await_response=False)

                except Exception as e:
                    logger.exception("Error registrando nodo %s: %s", name, e)
                    return Message(type=MessageType.DISCOVERY_HEARTBEAT_ACK, src=self.ip, dst=message.header.get("src"), payload={}, metadata = {"status": "ERROR", "error_msg": str(e)})
            
            # Retornar mensaje de éxito
            return Message(type=MessageType.DISCOVERY_HEARTBEAT_ACK, src=self.ip, dst=message.header.get("src"), payload={"ip": self.ip, "name": self.node_name}, metadata = {"status": "OK"})

        except Exception as e:
            logger.exception("Error en _handle_heartbeat: %s", e)
            return Message(type=MessageType.DISCOVERY_HEARTBEAT_ACK, src=self.ip, dst=message.header.get("src"), payload={}, metadata = {"status": "ERROR", "error_msg": str(e)})

    def _handle_query_by_name(self, message: Message):
        """ Maneja QUERY_BY_NAME
         Obteniendo la ip de un nodo dado su nombre
         Recibe: Message(... payload : {name : "node_name"} ...)
         Retorna: Message(... payload : {node: (node_name, node_ip, node_role, last_heartbeat)} ...)
        """

        try:
            name = (message.payload or {}).get("name")
            logger.info(f"[{self.node_name}] : QUERY_BY_NAME received from ({message.header.get('src')}) for {name}")
            
            if not name:
                return Message(type=MessageType.DISCOVERY_QUERY_BY_NAME_ACK, src=self.ip, dst=message.header.get("src"), payload={}, metadata={"status": "ERROR", "error_msg": "Missing name"})
            
            node = self.register_table.get_node(name)
            
            if not node:
                return Message(type=MessageType.DISCOVERY_QUERY_BY_NAME_ACK, src=self.ip, dst=message.header.get("src"), payload={}, metadata={"status": "ERROR", "error_msg": "Not found"})

            logger.info(f"[{self.node_name}] : Returning node : {str(node)})")
            return Message(type=MessageType.DISCOVERY_QUERY_BY_NAME_ACK, src=self.ip, dst=message.header.get("src"), payload={"node": node.to_dict()}, metadata={"status": "OK"})
        
        except Exception as e:
            logger.exception("Error en query_by_name: %s", e)
            return Message(type=MessageType.DISCOVERY_QUERY_BY_NAME_ACK, src=self.ip, dst=message.header.get("src"), payload={}, metadata={"status": "ERROR", "error_msg": str(e)})

    def _handle_query_by_role(self, message: Message):
        """ Maneja DISCOVERY_QUERY_BY_ROLE
        Recibe:
            Message = ( ... payload : { "role": "<NODE_ROLE>" } ... )
        Retorna:
            Message = ( ... payload : { "nodes": [{"name": name1, "ip": ip1}, {"name": name2, "ip": ip2}, ...] } ... )"""
        
        try:
            # Payload del mensaje recibido
            payload = message.payload or {}
            role = payload.get("role")

            logger.info(f"[{self.node_name}] : QUERY_BY_ROLE received from ({message.header.get('src')}) for {role}")

            if not role:
                return Message(type=MessageType.DISCOVERY_QUERY_BY_ROLE_ACK, src=self.ip, dst=message.header.get("src"), payload={}, metadata={"status": "ERROR", "error_msg": "Missing role"})

            # Obtener rol
            try:
                node_role = NodeType(role)

            except Exception:
                return Message(type=MessageType.DISCOVERY_QUERY_BY_ROLE_ACK, src=self.ip, dst=message.header.get("src"), payload={}, metadata={"status": "ERROR", "error_msg": "Invalid role"})

            # Obtener nodos registrados con ese rol
            nodes = self.register_table.get_nodes_by_role(node_role)

            # Preparar respuesta
            nodes_response = [ {"name": n.name, "ip": n.ip} for n in nodes ]

            logger.info(f"[{self.node_name}] : QUERY_BY_ROLE returning : {nodes_response}")

            return Message(type=MessageType.DISCOVERY_QUERY_BY_ROLE_ACK, src=self.ip, dst=message.header.get("src"), payload={"nodes": nodes_response}, metadata={"status": "OK"})

        except Exception as e:
            logger.info("Error en query_by_role: %s", e)            
            return Message(type=MessageType.DISCOVERY_QUERY_BY_ROLE_ACK, src=self.ip, dst=message.header.get("src"), payload={}, metadata={"status": "ERROR", "error_msg": str(e)})


    def _handle_query_all(self, message: Message):
        """ Maneja QUERY_ALL
         Obtiene todos los nodos registrados en la tabla
         Recibe: Message(... payload : {} ...) 
         RetornaL Message(... payload: {nodes : [ (node_name_1, node_ip_1, node_role_1, last_heartbeat_1) ... ] ... })"""
        
        try:
            nodes = self.register_table.get_all_nodes()
            return Message(type=MessageType.DISCOVERY_QUERY_ALL_ACK, src=self.ip, dst=message.header.get("src"), payload={"nodes": [n.to_dict() for n in nodes]}, metadata = {"status": "OK"})
        
        except Exception as e:
            logger.exception("Error en query_all: %s", e)
            return Message(type=MessageType.DISCOVERY_QUERY_ALL_ACK, src=self.ip, dst=message.header.get("src"), payload={}, metadata={"status": "ERROR", "error_msg": str(e)})

    # ---------------- Background loops ----------------
    def _update_peers(self):
        """ Hilo que periódicamente envía señales a toda la subred buscando otros discovery nodes 
           . Actualiza lista de peers con los Discovery Nodes que respondan"""

        logger.info("%s: iniciando _update_peers", self.node_name)
        while not self._stop.is_set():
            try:
                found = {}
                # Envía señales a todas las ips de la red en paralelo
                results = self._find_peers_in_parallel()

                for _ , response in results:
                    if not response:
                        continue
                    try:
                        # Procesa la respuesta para convertirla en name , ip
                        peer_name, peer_ip = self._process_peer_discovery_response(response)
                        found[peer_name] = peer_ip

                    except Exception:
                        continue
                # Actualiza peers si hubo cambios
                self._update_peers_list(found)

                # Espera hasta próximo descubrimiento
                time.sleep(self.discovery_interval)

            except Exception as e:
                logger.exception(f"Error en _update_peers: {str(e)}")
                time.sleep(self.discovery_interval)

    def clean_inactive_register_loop(self):
        """ Hilo para limpiar nodos inactivos de la tabla de registros cada cierto tiempo."""

        logger.info("%s: iniciando clean_inactive_register_loop", self.node_name)

        while not self._stop.is_set():
            try:
                time.sleep(self.clean_interval)

                # Determinar nodos inactivos
                now = time.time()
                dead = [n.name for n in self.register_table.get_all_nodes() if now - n.last_heartbeat > self.heartbeat_timeout]
                
                # Eliminarlos de la tabla
                for name in dead:
                    logger.info("%s: eliminando nodo inactivo %s", self.node_name, name)
                    n = self.register_table.remove_node(name)
                    
                    for peer_ip in self.peers.values():
                        repl_msg = Message(MessageType.GOSSIP_UPDATE, self.ip, peer_ip, payload={"op": "delete", "registry": n.to_dict()})
                        self.send_message(peer_ip, 9000, repl_msg, await_response=False)
            
            except Exception:
                logger.exception("Error en clean_inactive_register_loop")
                time.sleep(self.clean_interval)

    def _find_peers_in_parallel(self):
        """ Envía señales en paralelo a toda la red para encontrar otros Discovery Nodes"""
        max_workers = min(self.discovery_workers, max(1, len(self.possible_ips)))
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(self._probe_send_heartbeat, ip) for ip in self.possible_ips]
            for fut in concurrent.futures.as_completed(futures):
                try:
                    res = fut.result(timeout=self.discovery_timeout + 0.5)
                except Exception:
                        res = (None, None)
                results.append(res)

        return results

    def _probe_send_heartbeat(self, ip_addr: str):
        """ Envía un DISCOVERY_HEARTBEAT a ip_addr; devuelve (ip, response)"""
        try:
            msg = Message(type=MessageType.DISCOVERY_HEARTBEAT, src=self.ip, dst=ip_addr, payload={"name": self.node_name, "ip": self.ip, "role": "DISCOVERY"})
            resp = self.send_message(ip_addr, self.port, msg, await_response=True, timeout=self.discovery_timeout)
            return ip_addr, resp
        except Exception:
            return ip_addr, None

    def _process_peer_discovery_response(self, response: Message): 
        """ Obtiene el nombre y direccion ip de un peer de una respuesta de heartbeat"""
        if response.header.get("type") == MessageType.DISCOVERY_HEARTBEAT_ACK and response.metadata.get("status") == "OK":
            peer_name = response.payload.get("name")
            peer_ip = response.payload.get("ip")

            if peer_name and peer_ip:
                return peer_name, peer_ip
            
        raise Exception("Invalid heartbeat response")
    
    def _update_peers_list(self, discovered_peers: dict):
        """ Actualiza la lista de peers si hay cambios, 
            .En caso de ser el coordinador(menor nombre) hace merge con uno de los nuevos nodos y
            envia nuevo estado al resto de nodos.
        """
        current_peers = list(self.peers.keys())
        current_peers.append(self.node_name)
        coordinador = min(current_peers)
        
        new_peers = {}
        with self.peers_lock:
            for peer_name in discovered_peers.keys():

                if peer_name == self.node_name:
                    continue

                if peer_name not in self.peers.keys():
                    new_peers[peer_name] = discovered_peers[peer_name]
                    self.peers[peer_name] = discovered_peers[peer_name]

        if new_peers:
            logger.info("[%s] Nuevos peers descubiertos: %s", self.node_name, list(new_peers.keys()))

            if self.node_name == coordinador:
                # Elegir un único nodo nuevo para merge
                nodo_merge = min([p["name"] for p in new_peers])
                peer_ip = next(p["ip"] for p in new_peers if p["name"] == nodo_merge)

                # Merge lo inicia el nodo con menor nombre entre coordinador y nodo_merge
                if self.node_name < nodo_merge:
                    try:
                        with self.merging_lock:
                            logger.info("[%s] Merge de estado con peer %s (%s)", self.node_name, nodo_merge, peer_ip)
                            self._merge_state(peer_ip)

                            # Enviar el estado al resto de nodos
                            for dst_ip in self.peers.values():

                                if dst_ip == peer_ip:
                                    continue 

                                self.send_state(dst_ip)

                    except Exception:
                        logger.exception("[%s] Error durante merge con peer %s", self.node_name, nodo_merge)

    # Gossip Methods
    def _on_gossip_update(self, update : dict):
        op = update.get("op")
        registry = ServiceRegister.from_dict(update.get("registry"))

        if not op or not registry:
            return

        if op == 'add':
            self.register_table.add_node(registry)

        elif op == 'delete':
            self.register_table.remove_node(registry.name)

    def _merge_state(self, peer_ip):
        data = self._export_register_table()

        merge_msg = Message(MessageType.MERGE_STATE, self.ip, peer_ip, payload={"nodes": data})

        try:
            logger.info("[%s] Enviando MERGE_STATE a %s", self.node_name, peer_ip)
            response = self.send_message(peer_ip, 9000, merge_msg, await_response=True)

            if response and response.payload.get("nodes"):
                self._import_register_table(response.payload["nodes"])

        except Exception as e:
            logger.exception("[%s] Error durante MERGE_STATE con %s: %s", self.node_name, peer_ip, e)

    def _handle_merge_state(self, message):
        try:
            payload = message.payload or {}
            nodes_data = payload.get("nodes", [])

            self._import_register_table(nodes_data)

            data = self._export_register_table()

            return Message(MessageType.MERGE_STATE_ACK, self.ip, message.header.get("src"), payload={"nodes": data})

        except Exception as e:
            logger.exception("Error en _handle_merge_state: %s", e)
            return Message(MessageType.MERGE_STATE_ACK, self.ip, message.header.get("src"), payload={})

    def send_state(self, peer_ip):
        data = self._export_register_table()

        msg = Message(MessageType.SEND_STATE, self.ip, peer_ip, payload={"nodes": data})

        try:
            logger.info("[%s] Enviando MERGE_STATE a %s", self.node_name, peer_ip)
            self.send_message(peer_ip, 9000, msg, await_response=False)

        except Exception as e:
            logger.exception("[%s] Error durante SEND_STATE con %s: %s", self.node_name, peer_ip, e)

    def handle_send_state(self, message):
        try:
            payload = message.payload or {}
            nodes_data = payload.get("nodes", [])

            self._import_register_table(nodes_data)

        except Exception as e:
            logger.exception("Error en _handle_send_state: %s", e)


    def _export_register_table(self):
        return [n.to_dict() for n in self.register_table.get_all_nodes()]

    def _import_register_table(self, nodes:list[dict]):
        for data in nodes:
            try:
                node = ServiceRegister.from_dict(data)
                self.register_table.add_node(node)
            except Exception:
                logger.exception("[%s] Error importing node %s", self.node_name, data)