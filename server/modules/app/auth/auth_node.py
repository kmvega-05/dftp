import json
import os
import bcrypt
import threading
import logging

from server.modules.discovery import NodeType
from server.modules.consistency import GossipNode
from server.modules.comm import Message, MessageType

logger = logging.getLogger("dftp.auth.auth_node")

class AuthNode(GossipNode):
    """
    Nodo de autenticación (AuthNode) con replicación gossip.
    """

    def __init__(self, node_name: str, ip: str, port: int, discovery_timeout: float = 0.8, heartbeat_interval: int = 2, discovery_workers: int = 32):
        
        self._users_lock = threading.Lock()
        self._ensure_users_file()

        super().__init__(node_name=node_name, ip=ip, port=port, discovery_timeout=discovery_timeout, heartbeat_interval=heartbeat_interval, node_role=NodeType.AUTH, discovery_workers=discovery_workers)

        # Registrar handlers de autenticación
        self.register_handler(MessageType.AUTH_VALIDATE_USER, self._handle_validate_user)
        self.register_handler(MessageType.AUTH_VALIDATE_PASSWORD, self._handle_validate_password)

        logger.info("[%s] AuthNode iniciado en %s:%s", node_name, ip, port)

    # -------------------- Handlers de autenticación --------------------
    def _handle_validate_user(self, message: Message) -> Message:
        payload = message.payload or {}
        username = payload.get("username", "")
        result = self.user_exists(username)
        logger.info("[%s] VALIDATE_USER '%s', result=%s", self.node_name, username, result)
        return Message(type=MessageType.AUTH_VALIDATE_USER_ACK, src=self.ip, dst=message.header.get("src"), payload={"result": result})

    def _handle_validate_password(self, message: Message) -> Message:
        payload = message.payload or {}
        username = payload.get("username", "")
        password = payload.get("password", "")
        result = self.validate_password(username, password)
        logger.info("[%s] VALIDATE_PASSWORD '%s', result=%s", self.node_name, username, result)
        return Message(type=MessageType.AUTH_VALIDATE_PASSWORD_ACK, src=self.ip, dst=message.header.get("src"), payload={"result": result})

    # -------------------- Acceso a usuarios --------------------
    def get_users_file_path(self) -> str:
        return os.path.join(os.path.dirname(__file__),'data', 'users.json')

    def get_user_by_name(self, username: str) -> dict | None:
        with self._users_lock:
            try:
                with open(self.get_users_file_path(), 'r') as f:
                    data = json.load(f)
                for user in data.get('users', []):
                    if user.get('username') == username:
                        return user
            except Exception as e:
                logger.error("Error leyendo users.json: %s", e)
        return None

    def user_exists(self, username: str) -> bool:
        return self.get_user_by_name(username) is not None

    def validate_password(self, username: str, password: str) -> bool:
        user = self.get_user_by_name(username)
        if user and 'password' in user:
            try:
                return bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8'))
            except Exception as e:
                logger.error("Error validando password de %s: %s", username, e)
        return False

    # -------------------- Inicialización de usuarios --------------------
    def _ensure_users_file(self):
        users_file = self.get_users_file_path()
        users_dir = os.path.dirname(users_file)
        try:
            os.makedirs(users_dir, exist_ok=True)
            if os.path.exists(users_file):
                return
            self._create_sample_users(users_file)
        except Exception as e:
            logger.exception("[%s] Error inicializando users.json: %s", self.node_name, e)
            raise

    def _create_sample_users(self, users_file: str):
        users = [
            {"username": "test", "password": bcrypt.hashpw(b"test123", bcrypt.gensalt()).decode("utf-8")},
            {"username": "admin", "password": bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode("utf-8")}
        ]
        with open(users_file, "w") as f:
            json.dump({"users": users}, f, indent=4)

    # -------------------- Métodos Gossip --------------------
    def _on_gossip_update(self, update: dict):
        """Aplica cambios recibidos via gossip (add/delete)."""
        op = update.get("op")
        user = update.get("user")
        if not op or not user:
            return

        with self._users_lock:
            data = {"users": []}
            try:
                with open(self.get_users_file_path(), 'r') as f:
                    data = json.load(f)
            except FileNotFoundError:
                pass

            if op == "add":
                # update: si no existe agregar, si existe actualizar
                for idx, u in enumerate(data["users"]):
                    if u["username"] == user["username"]:
                        data["users"][idx] = user
                        break
                else:
                    data["users"].append(user)

            elif op == "delete":
                data["users"] = [u for u in data["users"] if u["username"] != user["username"]]

            with open(self.get_users_file_path(), 'w') as f:
                json.dump(data, f, indent=4)

    def _merge_state(self, peer_ip: str):
        """Inicia un merge bidireccional con peer_ip."""
        # Leer estado propio
        with self._users_lock:
            try:
                with open(self.get_users_file_path(), 'r') as f:
                    local_data = json.load(f)
            except FileNotFoundError:
                local_data = {"users": []}

        msg = Message(type=MessageType.MERGE_STATE, src=self.ip, dst=peer_ip, payload=local_data)
        try:
            logger.info("[%s] Enviando MERGE_STATE a %s", self.node_name, peer_ip)
            # Esperar respuesta con estado del peer
            response = self.send_message(peer_ip, 9000, msg, await_response=True, timeout=30)

            logger.info("[%s] Recibido MERGE_STATE_ACK de %s", self.node_name, peer_ip)

            # Aplicar el estado recibido del peer
            if response and response.payload.get("users"):
                for user in response.payload["users"]:
                    self._on_gossip_update({"op": "add", "user": user})

            logger.info("[%s] MERGE_STATE completado con %s", self.node_name, peer_ip)

        except Exception as e:
            logger.exception("[%s] Error durante MERGE_STATE con %s: %s", self.node_name, peer_ip, e)

    def _handle_merge_state(self, message: Message) -> Message:
        """
        Recibe MERGE_STATE de otro nodo, aplica los usuarios y retorna
        MERGE_STATE_ACK con el estado propio.
        """

        logger.info("[%s] Recibiendo MERGE_STATE de %s", self.node_name, message.header.get("src"))
        # Aplicar usuarios recibidos
        for user in message.payload.get("users", []):
            self._on_gossip_update({"op": "add", "user": user})

        # Leer estado propio para devolverlo
        with self._users_lock:
            try:
                with open(self.get_users_file_path(), 'r') as f:
                    local_data = json.load(f)
            except FileNotFoundError:
                local_data = {"users": []}
        
        logger.info("[%s] Enviando MERGE_STATE_ACK a %s", self.node_name, message.header.get("src"))
        return Message(type=MessageType.MERGE_STATE_ACK, src=self.ip, dst=message.header.get("src"), payload=local_data)
    
    def send_state(self, peer_ip: str):
        """Envía el estado propio a otro nodo sin esperar respuesta."""
        with self._users_lock:
            try:
                with open(self.get_users_file_path(), 'r') as f:
                    local_data = json.load(f)
            except FileNotFoundError:
                local_data = {"users": []}

        msg = Message(type=MessageType.SEND_STATE, src=self.ip, dst=peer_ip, payload=local_data)
        try:
            logger.info("[%s] Enviando SEND_STATE a %s", self.node_name, peer_ip)
            self.send_message(peer_ip, 9000, msg, await_response=False)
            logger.info("[%s] SEND_STATE completado con %s", self.node_name, peer_ip)

        except Exception:
            logger.exception("[%s] Error enviando SEND_STATE a %s", self.node_name, peer_ip)
            
    def _handle_send_state(self, message: Message):
        """Recibe SEND_STATE de otro nodo y actualiza el estado local sin responder."""
        users = message.payload.get("users", [])
        for user in users:
            self._on_gossip_update({"op": "add", "user": user})

        logger.info("[%s] Estado actualizado desde SEND_STATE de %s", self.node_name, message.header.get('src'))


    # -------------------- Métodos públicos --------------------
    def add_user(self, username: str, password: str):
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        user = {"username": username, "password": hashed}
        with self._users_lock:
            data = {"users": []}
            try:
                with open(self.get_users_file_path(), 'r') as f:
                    data = json.load(f)
            except FileNotFoundError:
                pass

            if any(u["username"] == username for u in data["users"]):
                return False
            
            data["users"].append(user)

            with open(self.get_users_file_path(), 'w') as f:
                json.dump(data, f, indent=4)

        self.notify_local_change({"op": "add", "user": user})
        return True

    def update_user(self, username: str, password: str):
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        user = {"username": username, "password": hashed}
        self._on_gossip_update({"op": "add", "user": user})
        self.notify_local_change({"op": "add", "user": user})
        return True

    def delete_user(self, username: str):
        self.notify_local_change({"op": "delete", "user": {"username": username}})
        self._on_gossip_update({"op": "delete", "user": {"username": username}})
        return True
