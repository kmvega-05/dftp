from typing import Optional
import socket
import logging

logger = logging.getLogger("dftp.routing.client_session")

class ClientSession:
    """
    Representa una sesión FTP asociada a un cliente.

    Toda modificación del estado debe realizarse exclusivamente
    mediante métodos públicos (no acceso directo a atributos).
    """

    def __init__(self, session_id: str, client_ip: str, control_socket: Optional["socket.socket"] = None):
        self.session_id = session_id
        self._client_ip = client_ip
        self._control_socket = control_socket

        self.reset_session()

    # -------------------- Session lifecycle --------------------

    def reset_session(self) -> None:
        """
        Resetea la sesión a su estado inicial.
        Usado típicamente tras QUIT o al crear una nueva sesión.
        """
        self._username: Optional[str] = None
        self._authenticated: bool = False
        self._cwd: str = "/"

        # Data connection
        self._data_ip: Optional[str] = None
        self._data_port: Optional[int] = None
        self._pasv_mode: bool = False
        self._transfer_type: str = "A"  # por defecto ASCII

        # RNFR / RNTO
        self._rename_from_path: Optional[str] = None

    def get_session_id(self) -> str:
        return self.session_id 

    def get_client_ip(self) -> str:
        """Retorna la IP del cliente asociada a la sesión."""
        return self._client_ip

    def is_closed(self) -> bool:
        """Retorna True si la sesión está cerrada (sin socket de control)."""
        return self._control_socket is None

    # -------------------- User / auth --------------------

    def change_user(self, username: str) -> None:
        """
        Cambia el usuario de la sesión.
        Invalida automáticamente la autenticación.
        """
        self._username = username
        self._authenticated = False
        self.clear_rename_from()

    def authenticate(self) -> None:
        """
        Marca la sesión como autenticada.
        """
        if not self._username:
            raise RuntimeError("Cannot authenticate without username")
        self._authenticated = True

    def is_authenticated(self) -> bool:
        return self._authenticated

    def get_username(self):
        return self._username

    # -------------------- Working directory --------------------

    def get_cwd(self) -> str:
        return self._cwd

    def set_cwd(self, new_cwd: str) -> None:
        """
        Establece el directorio de trabajo actual.
        Se asume que la validación se hace en el Processing/Data node.
        """
        self._cwd = new_cwd

    # -------------------- Rename (RNFR / RNTO) --------------------

    def set_rename_from(self, path: str) -> None:
        self._rename_from_path = path

    def get_rename_from(self) -> Optional[str]:
        return self._rename_from_path

    def clear_rename_from(self) -> None:
        self._rename_from_path = ""

    # -------------------- Passive / Active mode --------------------

    def enter_pasv_mode(self, ip: str, port: int) -> None:
        """
        Activa modo pasivo y guarda la info necesaria
        para que el cliente se conecte al DataNode.
        """
        self._pasv_mode = True
        self._data_ip = ip
        self._data_port = port

    def pasv_mode_enabled(self) -> bool:
        return self._pasv_mode

    def get_pasv_mode_info(self) -> Optional[tuple[str, int]]:
        """
        Retorna (ip, port) si la sesión está en modo pasivo,
        o None si no lo está.
        """
        if not self._pasv_mode:
            return None
        return self._data_ip, self._data_port

    def clear_pasv(self) -> None:
        """
        Limpia cualquier estado de conexión de datos.
        Llamar tras completar una transferencia.
        """
        self._pasv_mode = False
        self._data_ip = None
        self._data_port = None

    # ------------------- Transfer Type  ---------------------
    def set_transfer_type(self, t: str) -> None:
        """Establece el tipo de transferencia ('A', 'I', etc.)."""
        if t.upper() not in ("A", "I", "E", "L"):
            raise ValueError(f"Invalid transfer type: {t}")
        self._transfer_type = t.upper()

    def get_transfer_type(self) -> str:
        """Retorna el tipo de transferencia actual."""
        return self._transfer_type

    # -------------------- Control socket --------------------

    def set_control_socket(self, sock: "socket.socket") -> None:
        self._control_socket = sock

    def send_response(self, code: int, message: str) -> None:
        """
        Envía una respuesta al cliente a través del socket de control.
        Formato RFC-959: "CODE message\r\n"
        """
        if not self._control_socket:
            logger.warning("No control socket set for session %s", self.session_id)
            return

        try:
            line = f"{code} {message}\r\n"
            self._control_socket.sendall(line.encode("utf-8"))
            logger.info("Sent to %s: %s", self._client_ip, line.strip())

        except Exception:
            logger.exception("Failed to send response to %s", self._client_ip)

    def recv_lines(self):
        """
        Recibe datos por parte del cliente y lo separa en líneas"""
        buffer = ""

        for chunk in self._recv_chunks():
            buffer += chunk.decode('utf-8', errors='replace')

            while '\r\n' in buffer:
                line, buffer = buffer.split('\r\n', 1)
                line = line.strip()
                yield line

        # En caso de que quede algo en el buffer
        if buffer.strip():
            yield buffer.strip()

    def _recv_chunks(self, chunk_size: int = 65536):
        try:
            while True:
                chunk = self._control_socket.recv(chunk_size)
                
                if not chunk:
                    break

                yield chunk
        
        except Exception as e:
            logger.debug("recv_chunks: socket read interrupted: %s", e)
            return

    # ------------------ Serialización/ Deserialización -------------------
    def to_json(self) -> dict:
        """Serializa la sesión para enviarla en un mensaje."""
        return {
            "session_id": self.session_id,
            "client_ip": self._client_ip,
            "username": self._username,
            "authenticated": self._authenticated,
            "cwd": self._cwd,
            "pasv_mode": self._pasv_mode,
            "data_ip": self._data_ip,
            "data_port": self._data_port,
            "transfer_type": self._transfer_type,
            "rename_from": self._rename_from_path,
        }

    @classmethod
    def from_json(cls, data: dict) -> "ClientSession":
        """Crea una sesión desde un diccionario recibido."""
        session = cls(session_id=data["session_id"], client_ip=data.get("client_ip", "0.0.0.0"))
        session.update_session(data)
        return session

    def update_session(self, data: dict) -> bool:
        """
        Actualiza el estado de la sesión con los datos recibidos.
        Retorna True si hubo algún cambio, False si todo era igual.
        """
        changed = False

        if not data:
            return False
        
        new_username = data.get("username")
        new_auth = data.get("authenticated")
        new_cwd = data.get("cwd")
        new_pasv_mode = data.get("pasv_mode")
        new_data_ip = data.get("data_ip")
        new_data_port = data.get("data_port")
        new_transfer_type = data.get("transfer_type")
        new_rnfr = data.get("rename_from")

        if  new_username is not None and self._username != new_username:
            self._username = new_username
            changed = True

        if new_auth is not None and self._authenticated != new_auth:
            self._authenticated = new_auth
            changed = True

        if new_cwd is not None and self._cwd != new_cwd:
            self._cwd = new_cwd
            changed = True

        if new_pasv_mode is not None and self._pasv_mode != new_pasv_mode:
            self._pasv_mode = new_pasv_mode
            changed = True

        if new_data_ip is not None and self._data_ip != new_data_ip:
            self._data_ip = new_data_ip
            changed = True

        if new_data_port is not None and self._data_port != new_data_port:
            self._data_port = new_data_port
            changed = True
        
        if new_transfer_type is not None and self._transfer_type != new_transfer_type:
            self.set_transfer_type(new_transfer_type)
            changed = True

        if new_rnfr is not None and self._rename_from_path != new_rnfr:
            self._rename_from_path = new_rnfr
            changed = True

        return changed

    # -------------------- Debug / logging --------------------

    def __str__(self) -> str:
       return (
        f"ClientSession("
        f"user={self._username or 'anonymous'}, "
        f"CWD={self._cwd}, "
        f"Mode={'PASV' if self._pasv_mode else 'ACTIVE'}, "
        f"Transfer={self._transfer_type}"
        f")"
    )
