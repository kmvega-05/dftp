import logging
import socket
import threading
import uuid
from entities.file_system_manager import _GLOBAL_FSM as fs_manager

logger = logging.getLogger(__name__)

class ClientSession:
    """Representa el estado de sesión de un cliente FTP."""

    def __init__(self, client_address=None):
        # Lock para proteger el estado de la sesión
        self.lock = threading.RLock()

        # Lock para serializar envíos por la conexión de control
        self.control_lock = threading.RLock()

        # Identificación de la conexión
        self.client_address = client_address

        # Estado de autenticación / paths
        self.username = None
        self.authenticated = False
        self.current_directory = "/"
        self.root_directory = None

        # PASV / data connection state
        self.data_socket = None
        self.data_port = None
        self.pasv_mode = False

        self.rename_from_path = None
        self.active_transfers = {}
        self.pending_quit = False

    # ----------------- user / auth -----------------
    def set_username(self, username: str):
        """Establece el nombre de usuario y limpia el estado relevante."""
        with self.lock:
            # conservar client_address pero limpiar estado previo
            self.username = username
            self.authenticated = False
            self.current_directory = "/"
            self.root_directory = None
            self.rename_from_path = None
            logger.info("Username set to: %s", username)

    def authenticate(self):
        """Marca la sesión como autenticada y establece el root del usuario."""
        with self.lock:
            self.authenticated = True
            self.root_directory = fs_manager.get_user_root(self.username)
            logger.info("User %s authenticated successfully", self.username)

    def is_authenticated(self) -> bool:
        """Indica si la sesión está autenticada."""
        with self.lock:
            return self.authenticated

    # ----------------- rename helpers -----------------
    def set_rename_from(self, path: str):
        """Registra el path origen para la operación RNFR."""
        with self.lock:
            self.rename_from_path = path

    def get_rename_from(self):
        """Devuelve el path registrado por RNFR o None."""
        with self.lock:
            return self.rename_from_path

    def clear_rename_from(self):
        """Limpia el estado de RNFR."""
        with self.lock:
            self.rename_from_path = None

    # ----------------- session lifecycle -----------------
    def reset_session(self, client_address=None):
        """Reinicializa el estado de la sesión sin recrear el lock.

        Cierra conexiones de datos y cancela transferencias activas.
        """
        with self.lock:
            # limpiar PASV y transferencias
            self.cleanup_pasv()
            self.cancel_all_transfers()

            # actualizar client_address si se pasa
            if client_address is not None:
                self.client_address = client_address

            # Reiniciar campos de sesión pero mantener el lock y la estructura
            self.username = None
            self.authenticated = False
            self.current_directory = "/"
            self.root_directory = None
            self.rename_from_path = None
            logger.info("Session reset for %s", self.client_address)

    def reinitialize(self):
        """Aplicar el comportamiento RFC-959 REIN: restablecer credenciales y
        parámetros de sesión al estado inicial sin cancelar transferencias
        activas ni cerrar conexiones de datos.

        Esto deja la conexión de control abierta; permite que transferencias en
        curso continúen usando sus sockets/recursos. No modifica
        `active_transfers`, `data_socket` ni `pasv_mode`.
        """
        with self.lock:
            self.username = None
            self.authenticated = False
            self.current_directory = "/"
            self.root_directory = None
            self.rename_from_path = None
            logger.info("Session reinitialized (REIN) for %s", self.client_address)

    def request_quit(self) -> bool:
        """Marcar la sesión para cierre (QUIT). Retorna True si no hay
        transferencias activas y el servidor puede cerrar la conexión de
        control inmediatamente. Si hay transferencias activas, setea
        `pending_quit` y retorna False.
        """
        with self.lock:
            self.pending_quit = True
            has_transfers = len(self.active_transfers) > 0
            return not has_transfers
    
    def is_quit_pending(self) -> bool:
        """Devuelve True si se pidió QUIT y está pendiente de cierre."""
        with self.lock:
            return bool(self.pending_quit)
    
    #------------------ response sending -----------------
    
    def send_response(self, client_socket: "socket.socket", code: int, message: str) -> None:
        """Envía una respuesta al cliente por `client_socket` con formato RFC-959.

        Esta ayuda centraliza el envío y el logging. No lanza excepciones al llamar.
        """
        try:
            line = f"{code} {message}\r\n"
            # Serializar envíos en la conexión de control
            with self.control_lock:
                client_socket.sendall(line.encode('utf-8'))
            logger.info("Sent response to %s: %s", self.client_address, line.strip())
        except Exception:
            logger.exception("Failed to send response to %s: %s", self.client_address, line)

    # ----------------- PASV / data socket -----------------
    def set_pasv(self, data_socket, data_port: int):
        """Configura la información PASV para la sesión."""
        with self.lock:
            self.data_socket = data_socket
            self.data_port = data_port
            self.pasv_mode = True
            logger.info("PASV listening on port %s for %s", data_port, self.client_address)

    def get_pasv_info(self):
        """Retorna (data_socket, data_port) o (None, None)."""
        with self.lock:
            return self.data_socket, self.data_port

    def cleanup_pasv(self):
        """Cierra y limpia la conexión PASV si existe."""
        with self.lock:
            if self.data_socket:
                try:
                    self.data_socket.close()
                    logger.info("Data socket closed for %s", self.client_address)
                except Exception as e:
                    logger.exception("Error closing data socket: %s", e)
            self.data_socket = None
            self.data_port = None
            self.pasv_mode = False
            logger.debug("PASV state cleaned up for %s", self.client_address)

    # ----------------- transfers management -----------------
    def start_transfer(self, transfer_obj, transfer_id: str = None) -> str:
        """Registra una transferencia activa y retorna su id.

        transfer_obj debe exponer un método `cancel()` que se pueda invocar
        desde otro hilo para abortar la transferencia.
        """
        with self.lock:
            if transfer_id is None:
                transfer_id = uuid.uuid4().hex[:8]
            self.active_transfers[transfer_id] = transfer_obj
        return transfer_id

    def can_close(self) -> bool:
        """Devuelve True si la sesión ha pedido QUIT y no hay transferencias activas.

        Esta comprobación se hace bajo lock para evitar condiciones de carrera.
        """
        with self.lock:
            return bool(self.pending_quit) and len(self.active_transfers) == 0
    

    def finish_transfer(self, transfer_id: str):
        """Marca una transferencia como finalizada y la elimina del registro."""
        with self.lock:
            return self.active_transfers.pop(transfer_id, None)

    def cancel_transfer(self, transfer_id: str) -> bool:
        """Intenta cancelar la transferencia indicada; retorna True si existía."""
        with self.lock:
            t = self.active_transfers.get(transfer_id)
            if not t:
                return False
        # llamar a cancel fuera del lock para evitar deadlocks si cancel espera
        try:
            cancel = getattr(t, 'cancel', None)
            if callable(cancel):
                cancel()
            else:
                # si no tiene cancel, intentamos cerrar sockets si existen
                sock = getattr(t, 'data_socket', None)
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
        except Exception:
            pass
        # remover del registro
        with self.lock:
            self.active_transfers.pop(transfer_id, None)
        return True

    def cancel_all_transfers(self):
        """Cancela y elimina todas las transferencias activas."""
        with self.lock:
            ids = list(self.active_transfers.keys())
        for tid in ids:
            self.cancel_transfer(tid)

    def list_active_transfers(self):
        """Devuelve una lista copiada de ids de transferencias activas."""
        with self.lock:
            return list(self.active_transfers.keys())

    # ----------------- util -----------------
    def __str__(self):
        with self.lock:
            return f"ClientSession(addr={self.client_address}, user={self.username}, auth={self.authenticated})"

    