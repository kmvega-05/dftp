import threading
import logging
import time
import os

from server.modules.discovery import LocationNode, NodeType
from server.modules.comm import Message, MessageType

logger = logging.getLogger("dftp.gossip.gossip_node")

class GossipNode(LocationNode):
    """Nodo que permite replicación gossip."""

    def __init__(self, node_name: str, ip: str, port: int,discovery_timeout: float = 0.8, heartbeat_interval: int = 5, node_role: NodeType = None, discovery_workers: int = 32):
        super().__init__(node_name, ip, port, node_role=node_role, discovery_timeout=discovery_timeout, heartbeat_interval=heartbeat_interval, discovery_workers=discovery_workers)

        # ---------------- Gossip state ----------------
        self.peers: dict[str, str] = {}
        self.peers_lock = threading.Lock()
        self.merging_lock = threading.Lock()

        # Control de parada para hilos
        self._stop = threading.Event()

        # Handlers
        self.register_handler(MessageType.GOSSIP_UPDATE, self._handle_gossip_update)
        self.register_handler(MessageType.MERGE_STATE, self._handle_merge_state)
        self.register_handler(MessageType.SEND_STATE, self._handle_send_state)

        # ---------------- Hilo actualización peers ----------------
        self.peers_update_thread = threading.Thread(target=self._update_peers, daemon=True)
        self.peers_update_thread.start()

        time.sleep(heartbeat_interval * 2)
        logger.info("GossipNode '%s' iniciado en %s:%s", self.node_name, self.ip, self.port)

    # ----------------- Métodos abstractos para la clase hija -----------------
    def _on_gossip_update(self, update: dict):
        raise NotImplementedError("_on_gossip_update must be implemented by subclass")

    def _merge_state(self, peer_ip: str):
        raise NotImplementedError("_merge_state must be implemented by subclass")

    def send_state(self, peer_ip: str):
        raise NotImplementedError("send_state must be implemented by subclass")
    
    def _handle_merge_state(self, message: Message):
        raise NotImplementedError("_handle_merge_state must be implemented by subclass")
    
    def _handle_send_state(self, message: Message):
        raise NotImplementedError("_handle_send_state must be implemented by subclass")
                        
    # ----------------- Hilo de actualización de peers -----------------
    def _update_peers(self):
        logger.info("[%s] Iniciando hilo _update_peers", self.node_name)

        while not self._stop.is_set():
            try:
                discovered_peers = self.query_by_role(self.node_role) or []
                new_peers = []

                # Determinar coordinador: nodo con menor nombre
                current_peers = list(self.peers.keys())
                current_peers.append(self.node_name)
                coordinador = min(current_peers)

                with self.peers_lock:
                    # Eliminar peers que ya no aparecen en el descubrimiento actual
                    discovered_names = set()
                    for p in discovered_peers:
                        try:
                            if not p:
                                continue
                            name = p.get("name")
                            if name:
                                discovered_names.add(name)
                        except Exception:
                            continue

                    # Remover peers ausentes (posible caída o partición)
                    removed = []
                    for existing_name in list(self.peers.keys()):
                        if existing_name not in discovered_names:
                            # No eliminar nuestro propio nombre ni entradas vacías
                            try:
                                if existing_name == self.node_name:
                                    continue
                            except Exception:
                                pass
                            removed.append(existing_name)

                    for r in removed:
                        logger.info("[%s] Peer %s no responde en este ciclo: eliminando de peers", self.node_name, r)
                        self.peers.pop(r, None)

                    # Añadir nuevos peers descubiertos
                    for peer in discovered_peers:
                        if not peer:
                            continue
                        peer_name = peer.get("name")
                        peer_ip = peer.get("ip")
                        if not peer_name or not peer_ip or peer_name == self.node_name:
                            continue
                        if peer_name not in self.peers:
                            self.peers[peer_name] = peer_ip
                            new_peers.append(peer)

                if new_peers:
                    logger.info("[%s] Nuevos peers descubiertos: %s", self.node_name, [p["name"] for p in new_peers])

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
                                    logger.info("[%s] Merge con (%s) completado", self.node_name, peer_ip)
                                    for dst_ip in self.peers.values():
                                        if dst_ip == peer_ip:
                                            continue 
                                        self.send_state(dst_ip)
                            except Exception:
                                logger.exception("[%s] Error durante merge con peer %s", self.node_name, nodo_merge)                

            except Exception:
                logger.exception("[%s] Error en _update_peers", self.node_name)

            time.sleep(self.heartbeat_interval)

    # ----------------- Notificación de cambios locales -----------------
    def notify_local_change(self, change: dict, sync: bool = False, required_acks: int = None) -> bool:
        """
        Notifica cambios locales a los peers.
        
        Args:
            change: Diccionario con el cambio a replicar
            sync: Si True, espera confirmaciones de los peers (sincrónico, en paralelo)
            required_acks: Número de ACKs requeridos (si sync=True). 
                          Si es None, se usa la variable de entorno GOSSIP_REQUIRED_ACKS o mayoría
        
        Returns:
            True si la operación fue exitosa, False si sync=True y no llegaron suficientes ACKs
        """
        if not change:
            return True

        with self.peers_lock:
            peers_snapshot = list(self.peers.values())

        # Si no es sincrónico, solo enviar sin esperar
        if not sync:
            for peer_ip in peers_snapshot:
                try:
                    logger.info(f"[{self.node_name}] Notificando cambio a {peer_ip} : {change}")
                    msg = Message(type=MessageType.GOSSIP_UPDATE, src=self.ip, dst=peer_ip, payload=change)
                    self.send_message(peer_ip, 9000, msg, await_response=False)
                except Exception:
                    logger.info("[%s] Error enviando gossip update a %s", self.node_name, peer_ip)
            return True

        # Modo sincrónico: enviar en paralelo y contar confirmaciones
        if not peers_snapshot:
            logger.info("[%s] notify_local_change sync: sin peers, retornando OK", self.node_name)
            return True

        # Determinar cantidad de ACKs requeridos
        if required_acks is None:
            required_acks = int(os.getenv("GOSSIP_REQUIRED_ACKS", len(peers_snapshot) // 2 + 1))

        required_acks = min(required_acks, len(peers_snapshot))
        
        logger.info(f"[{self.node_name}] Enviando GOSSIP_UPDATE sync a {len(peers_snapshot)} peers, requiriendo {required_acks} ACKs")

        # Enviar mensajes en paralelo y recopilar resultados
        results = {}
        threads = []

        def send_and_collect(peer_ip):
            try:
                logger.info(f"[{self.node_name}] Enviando GOSSIP_UPDATE sync a {peer_ip}")
                msg = Message(type=MessageType.GOSSIP_UPDATE, src=self.ip, dst=peer_ip, payload=change)
                response = self.send_message(peer_ip, 9000, msg, await_response=True)
                results[peer_ip] = response is not None
                if response:
                    logger.info(f"[{self.node_name}] ACK recibido de {peer_ip}")
                else:
                    logger.warning(f"[{self.node_name}] No se recibió respuesta de {peer_ip} (timeout)")
            except Exception as e:
                logger.warning(f"[{self.node_name}] Error enviando a {peer_ip}: {e}")
                results[peer_ip] = False

        # Lanzar threads para enviar en paralelo
        for peer_ip in peers_snapshot:
            t = threading.Thread(target=send_and_collect, args=(peer_ip,), daemon=False)
            t.start()
            threads.append(t)

        # Esperar a que terminen todos los threads
        for t in threads:
            t.join()

        # Contar confirmaciones
        confirmed_count = sum(1 for response in results.values() if response)
        
        logger.info(f"[{self.node_name}] notify_local_change sync: {confirmed_count}/{len(peers_snapshot)} ACKs recibidos (requería {required_acks})")

        return confirmed_count >= required_acks

    # ----------------- Handler de gossip -----------------
    def _handle_gossip_update(self, message: Message):
        logger.info(f"Recibiendo update de {message.header['src']}")
        try:
            change = message.payload
            if not change:
                return Message(MessageType.GOSSIP_UPDATE, self.ip, message.header.get('src'), payload={"success": True})
            
            with self.merging_lock:
                result = self._on_gossip_update(change)
            
            # Retornar ACK de éxito
            return Message(MessageType.GOSSIP_UPDATE, self.ip, message.header.get('src'), payload={"success": result})
        except Exception as e:
            logger.exception("[%s] Error manejando GOSSIP_UPDATE de %s: %s", self.node_name, message.header.get('src'), e)
            # Retornar ACK de fallo
            return Message(MessageType.GOSSIP_UPDATE, self.ip, message.header.get('src'), payload={"success": False})

    # ----------------- Método para detener hilos -----------------
    def stop(self):
        """Detiene los hilos de actualización de peers."""
        self._stop.set()
        self.peers_update_thread.join(timeout=2)
        logger.info("[%s] GossipNode detenido", self.node_name)
