import threading
from server.modules.app.routing.client_session.client_session import ClientSession

class SessionTable:
    """Tabla simple para almacenar sesiones y permitir búsquedas
    por session_id y por client IP.

    - _by_id: session_id -> ClientSession
    - _by_ip: client_ip -> [session_id, ...] (orden de inserción)
    """

    def __init__(self):
        self._by_id: dict[str, ClientSession] = {}
        self._by_ip: dict[str, list[str]] = {}
        self._lock = threading.Lock()

    def add(self, session: ClientSession) -> None:
        sid = session.get_session_id()
        ip = session.get_client_ip()

        with self._lock:
            # registrar por id
            self._by_id[sid] = session

            # registrar por ip (en caso de reconexion actualiza la sesion)
            lst = self._by_ip.get(ip)

            if lst is None:
                self._by_ip[ip] = [sid]

            else:
                if sid in lst:
                    lst.remove(sid)
                lst.append(sid)

    def remove_by_id(self, session_id: str) -> None:
        with self._lock:
            session = self._by_id.pop(session_id, None)
            if not session:
                return

            ip = session.get_client_ip()
            lst = self._by_ip.get(ip)

            if not lst:
                return
            
            if session_id in lst:
                lst.remove(session_id)

            if not lst:
                # limpiar entradas vacías
                self._by_ip.pop(ip, None)

    def get_by_id(self, session_id: str) -> ClientSession | None:
        with self._lock:
            return self._by_id.get(session_id)

    def get_by_ip(self, ip: str) -> list[ClientSession]:
        with self._lock:
            ids = list(self._by_ip.get(ip, []))
            sessions = [self._by_id.get(sid) for sid in ids if sid in self._by_id]
        return sessions

    def get_all_sessions(self) -> list[ClientSession]:
        """Retorna una lista con todas las sesiones actualmente almacenadas."""
        with self._lock:
            return list(self._by_id.values())

