import json
import os
import bcrypt
import threading
import logging

from server.modules.discovery import LocationNode, NodeType
from server.modules.comm import Message, MessageType

logger = logging.getLogger("dftp.auth.auth_node")

class AuthNode(LocationNode):
    """
    Nodo de autenticación (AuthNode) para el servidor FTP distribuido.

    Funciones principales:
    - Validar existencia de usuarios.
    - Validar contraseñas.
    - Mantener la base de datos de usuarios en un archivo JSON.

    Recibe mensajes de tipo:
    - AUTH_VALIDATE_USER
    - AUTH_VALIDATE_PASSWORD
    """

    def __init__(self, node_name: str, ip: str, port: int, discovery_timeout: float = 0.8,
                 heartbeat_interval: int = 2, discovery_workers: int = 32):
        """
        Inicializa el AuthNode y registra handlers de mensajes.

        Args:
            node_name: Nombre del nodo.
            ip: IP del nodo.
            port: Puerto interno del nodo.
            discovery_timeout: Timeout de descubrimiento.
            heartbeat_interval: Intervalo de heartbeat.
            discovery_workers: Cantidad de hilos para discovery.
        """
        super().__init__(node_name, ip, port, NodeType.AUTH, discovery_timeout, heartbeat_interval, discovery_workers)

        self._users_lock = threading.Lock()
        self._ensure_users_file()

        # Registrar handlers de mensajes
        self.register_handler(MessageType.AUTH_VALIDATE_USER, self._handle_validate_user)
        self.register_handler(MessageType.AUTH_VALIDATE_PASSWORD, self._handle_validate_password)

        logger.info("[%s] AuthNode iniciado en %s:%s", node_name, ip, port)

    # -------------------- Handlers de mensajes --------------------

    def _handle_validate_user(self, message: Message) -> Message:
        """Maneja mensajes de tipo AUTH_VALIDATE_USER."""
        payload = message.payload or {}
        username = payload.get("username", "")
        result = self.user_exists(username)
        logger.info("[%s] Received VALIDATE_USER for '%s', result : %s", self.node_name, username, result)
        return Message(type=MessageType.AUTH_VALIDATE_USER_ACK, src=self.ip, dst=message.header.get("src"), payload={"result": result})

    def _handle_validate_password(self, message: Message) -> Message:
        """Maneja mensajes de tipo AUTH_VALIDATE_PASSWORD."""
        payload = message.payload or {}
        username = payload.get("username", "")
        password = payload.get("password", "")

        result = self.validate_password(username, password)
        logger.info("[%s] Received VALIDATE_PASSWORD for '%s,%s', result : %s", self.node_name, username, password, result)

        return Message(type=MessageType.AUTH_VALIDATE_PASSWORD_ACK, src=self.ip, dst=message.header.get("src"), payload={"result": result})

    # -------------------- Acceso a usuarios --------------------

    def get_users_file_path(self) -> str:
        """Obtiene la ruta al archivo JSON con la base de datos de usuarios."""
        return os.path.join(os.path.dirname(__file__), '..', 'data', 'users.json')

    def get_user_by_name(self, username: str) -> dict | None:
        """Busca un usuario por nombre."""
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
        """Verifica si un usuario existe en la base de datos."""
        return self.get_user_by_name(username) is not None

    def validate_password(self, username: str, password: str) -> bool:
        """Valida la contraseña de un usuario."""
        user = self.get_user_by_name(username)
        if user and 'password' in user:
            try:
                return bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8'))
            except Exception as e:
                logger.error("Error validando password de %s: %s", username, e)
        return False

    # -------------------- Inicialización de usuarios --------------------

    def _ensure_users_file(self):
        """Asegura que exista users.json; crea usuarios de prueba si no existe."""
        users_file = self.get_users_file_path()
        users_dir = os.path.dirname(users_file)

        try:
            os.makedirs(users_dir, exist_ok=True)

            if os.path.exists(users_file):
                logger.info("[%s] users.json encontrado", self.node_name)
                return

            logger.warning("[%s] users.json no existe, creando usuarios de prueba", self.node_name)
            self._create_sample_users(users_file)
            logger.info("[%s] users.json creado con usuarios de prueba", self.node_name)

        except Exception as e:
            logger.exception("[%s] Error inicializando users.json: %s", self.node_name, e)
            raise

    def _create_sample_users(self, users_file: str):
        """Crea usuarios de prueba en users.json."""
        users = [
            {"username": "test", "password": bcrypt.hashpw(b"test123", bcrypt.gensalt()).decode("utf-8")},
            {"username": "admin", "password": bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode("utf-8")}
        ]
        data = {"users": users}
        with open(users_file, "w") as f:
            json.dump(data, f, indent=4)
