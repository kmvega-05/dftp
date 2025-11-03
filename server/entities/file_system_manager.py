import os
import time
import posixpath
import uuid
import tempfile
import threading
from contextlib import contextmanager


BASE_DIRECTORY = "/tmp/ftp_root"


class SecurityError(Exception):
    """Excepción para errores de seguridad"""
    pass


class FileLockManager:
    """Administra locks por ruta (in-memory). Permite prevenir races locales.

    Provee un context manager `acquire(path)` para bloquear operaciones sobre
    una ruta concreta dentro del mismo proceso.
    """
    def __init__(self):
        """Inicializa el administrador de locks en memoria."""
        self._locks = {}
        self._global_lock = threading.Lock()

    @contextmanager
    def acquire(self, path):
        """Context manager que adquiere un lock reentrante para la ruta dada.

        Uso:
            with lock_mgr.acquire(path):
                # operación segura sobre path

        El lock es por ruta absoluta y evita races locales entre hilos.
        """
        key = os.path.abspath(path)
        with self._global_lock:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.RLock()
                self._locks[key] = lock
        lock.acquire()
        try:
            yield
        finally:
            lock.release()


class FileSystemManager:
    """Clase que expone una API segura y robusta para operaciones sobre el FS.

    Contrato resumido:
    - Todas las rutas externas (user) son "virtual paths" empezando con '/'.
    - Métodos aceptan user_root_directory y user_current_directory para resolución.
    - Los métodos lanzan SecurityError cuando hay path traversal.
    - Operaciones de escritura son atómicas: se escribe en temp y se hace os.replace.
    - Existen locks por ruta para evitar races locales.
    """

    def __init__(self, base_directory=BASE_DIRECTORY):
        self.base_directory = os.path.abspath(base_directory)
        self.lock_mgr = FileLockManager()
        # asegurar existencia del base
        os.makedirs(self.base_directory, exist_ok=True)

    # --------------------------- Path utilities ---------------------------
    def get_user_root(self, username):
        """Devuelve (y crea si hace falta) el directorio raíz real del usuario.

        username: nombre del usuario.
        Retorna la ruta absoluta en el filesystem donde se almacenan sus archivos.
        """
        user_dir = os.path.join(self.base_directory, username)
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

    def resolve_virtual(self, user_current_directory, requested_path):
        """Resuelve y normaliza una ruta virtual relativa o absoluta.

        Retorna la ruta virtual normalizada (ej: '/folder' o '/current/folder').
        """
        if requested_path.startswith('/'):
            return posixpath.normpath(requested_path)
        return posixpath.normpath(posixpath.join(user_current_directory, requested_path))

    def virtual_to_real(self, user_root_directory, virtual_path):
        """Convierte una ruta virtual a su ruta real en el filesystem.

        No valida la ruta; solo transforma la ruta virtual en una ruta absoluta
        bajo el `user_root_directory`.
        """
        clean = virtual_path.lstrip('/')
        real = os.path.normpath(os.path.join(user_root_directory, clean))
        return real

    def _ensure_within_root(self, user_root_directory, real_path):
        """Verifica que `real_path` esté dentro del `user_root_directory`.

        Resuelve symlinks antes de comparar para evitar escapes vía enlaces
        simbólicos. Lanza SecurityError si la ruta no pertenece al root.
        """
        root_real = os.path.realpath(user_root_directory)
        path_real = os.path.realpath(real_path)
        try:
            common = os.path.commonpath([root_real, path_real])
        except ValueError:
            # Different mount points or invalid paths
            raise SecurityError("Path traversal attempt detected")
        if common != root_real:
            raise SecurityError("Path traversal attempt detected")
        return True

    def secure_resolve(self, user_root_directory, user_current_directory, requested_path):
        """Resuelve una ruta solicitada y devuelve (virtual, real) validados.

        Asegura que la ruta real resultante quede dentro del root del usuario.
        Lanza SecurityError si hay intento de escape.
        """
        virtual = self.resolve_virtual(user_current_directory, requested_path)
        real = self.virtual_to_real(user_root_directory, virtual)
        self._ensure_within_root(user_root_directory, real)
        return virtual, real

    # --------------------------- Query operations -------------------------
    def exists(self, user_root_directory, user_current_directory, path, want='any'):
        """Resuelve la ruta y verifica existencia y tipo.

        Parámetros:
          - want: 'any' | 'file' | 'dir'

        Retorna (virtual, real) si la ruta existe y coincide con el tipo solicitado.

        Lanza:
          - SecurityError si hay intento de path traversal.
          - FileNotFoundError si no existe.
          - NotADirectoryError / IsADirectoryError si existe pero no coincide con el tipo.
        """
        virtual, real = self.secure_resolve(user_root_directory, user_current_directory, path)
        with self.lock_mgr.acquire(real):
            if not os.path.exists(real):
                raise FileNotFoundError("Path not found")

            if want == 'any':
                return virtual, real
            if want == 'file':
                if os.path.isfile(real):
                    return virtual, real
                raise IsADirectoryError("Not a file")
            if want == 'dir':
                if os.path.isdir(real):
                    return virtual, real
                raise NotADirectoryError("Not a directory")
            # Unknown want value
            raise ValueError(f"Invalid want parameter: {want}")

    def list_dir(self, user_root_directory, user_current_directory, path="."):
        """Lista los nombres dentro de un directorio virtual.
            Retorna una lista de nombres o una lista vacía si no es un directorio."""
        _, real = self.exists(user_root_directory, user_current_directory, path, want='dir')
        with self.lock_mgr.acquire(real):
            return os.listdir(real)

    def list_dir_detailed(self, user_root_directory, user_current_directory, path="."):
        """Devuelve una lista de diccionarios con metadatos (stat-like) para
        cada entrada dentro del directorio virtual `path`.

        Cada elemento de la lista tiene las mismas claves que `stat(...)`:
        name, path, size, permissions, modified, accessed, is_dir, is_file
        """
        _, real = self.exists(user_root_directory, user_current_directory, path, want='dir')
        results = []
        
        with self.lock_mgr.acquire(real):

            for entry in os.listdir(real):

                vpath = posixpath.join(self.resolve_virtual(user_current_directory, path), entry)
                info = self.stat(user_root_directory, user_current_directory, vpath)
                results.append(info)

        return results

    def stat(self, user_root_directory, user_current_directory, path):
        """Devuelve información básica (metadatos) del archivo o directorio.

        Retorna un diccionario con nombre, ruta virtual, tamaño, permisos y marcas
        de tiempo. Retorna None si no existe.
        """
        virtual, real = self.secure_resolve(user_root_directory, user_current_directory, path)
        if not os.path.exists(real):
            return None
        s = os.stat(real)
        return {
            'name': os.path.basename(virtual),
            'path': virtual,
            'size': s.st_size,
            'permissions': s.st_mode,
            'modified': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s.st_mtime)),
            'accessed': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s.st_atime)),
            'is_dir': os.path.isdir(real),
            'is_file': os.path.isfile(real),
        }

    # --------------------------- Directory ops ---------------------------
    def make_dir(self, user_root_directory, user_current_directory, new_dir_path):
        """Crea un directorio nuevo dentro del espacio del usuario.
            Retorna (True, message) en caso de éxito o (False, reason) en caso de error. """
        virtual, real = self.secure_resolve(user_root_directory, user_current_directory, new_dir_path)
        with self.lock_mgr.acquire(real):
            if os.path.exists(real):
                raise FileExistsError("Directory already exists")
            os.makedirs(real)
            return True, f'"{new_dir_path}" directory created'

    def remove_dir(self, user_root_directory, user_current_directory, dir_path):
        """Elimina un directorio si está vacío.
            Retorna (True, message) si se elimina, o (False, reason) en caso contrario."""
        # Resolve and validate; let exceptions propagate to caller
        _, real = self.exists(user_root_directory, user_current_directory, dir_path, want='dir')

        with self.lock_mgr.acquire(real):
            if os.listdir(real):
                raise OSError("Directory not empty")
            os.rmdir(real)
            return True, f'"{dir_path}" directory removed'

    def delete_file(self, user_root_directory, user_current_directory, file_path):
        """Elimina un archivo dentro del espacio del usuario.
            Retorna (True, message) o (False, reason)."""
        _, real = self.exists(user_root_directory, user_current_directory, file_path, want='file')

        with self.lock_mgr.acquire(real):
            if not os.path.exists(real):
                raise FileNotFoundError("File not found")
            os.remove(real)
            return True, f'"{file_path}" file deleted'

    def rename(self, user_root_directory, user_current_directory, old_path, new_path):
        """Renombra un archivo o directorio de forma segura.
            Retorna (True, message) en caso de éxito, o (False, reason) si falla."""
        
        _, old_real = self.secure_resolve(user_root_directory, user_current_directory, old_path)
        _, new_real = self.secure_resolve(user_root_directory, user_current_directory, new_path)

        lock1, lock2 = (old_real, new_real) if old_real <= new_real else (new_real, old_real)
        with self.lock_mgr.acquire(lock1):
            with self.lock_mgr.acquire(lock2):
                if not os.path.exists(old_real):
                    raise FileNotFoundError("Source path not found")
                if os.path.exists(new_real):
                    raise FileExistsError("Destination path already exists")
                os.rename(old_real, new_real)

    def generate_unique_filename(self, user_root_directory, user_current_directory, original_filename):
        """Genera un nombre único para un archivo en el directorio del usuario.

        Intenta evitar colisiones comprobando que el nombre no exista.
        """
        name, ext = os.path.splitext(original_filename)
        # Generate until free (robust but bounded by collision probability)
        for _ in range(10):
            unique_name = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
            try:
                _, real = self.secure_resolve(user_root_directory, user_current_directory, unique_name)
            except SecurityError:
                continue
            if not os.path.exists(real):
                return unique_name
        # worst-case fallback
        return f"{name}_{uuid.uuid4().hex[:8]}{ext}"

    # --------------------------- Atomic write / stream ------------------
    def store_stream(self, user_root_directory, user_current_directory, file_path, data_iterable, chunk_size=65536):
        """Guarda un archivo leyendo bytes desde un iterable.

        La operación es atómica: escribe en un fichero temporal y luego reemplaza
        el destino. Retorna (True, message) o (False, reason).
        """
        virtual, real = self.secure_resolve(user_root_directory, user_current_directory, file_path)
        parent = os.path.dirname(real)
        os.makedirs(parent, exist_ok=True)
        # Usar lock por archivo
        with self.lock_mgr.acquire(real):
            fd, tmp_path = tempfile.mkstemp(dir=parent)
            os.close(fd)
            total = 0
            try:
                with open(tmp_path, 'wb') as f:
                    for chunk in data_iterable:
                        if not chunk:
                            continue
                        f.write(chunk)
                        total += len(chunk)
                    f.flush()
                    os.fsync(f.fileno())
                # Reemplazar atómicamente
                os.replace(tmp_path, real)
                return True, f'"{file_path}" stored ({total} bytes)'
            except Exception as e:
                # Cleanup
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass
                return False, str(e)

    def retrieve_stream(self, user_root_directory, user_current_directory, file_path, chunk_size=65536):
        """Devuelve un generador que produce los chunks del archivo solicitado.

        El caller es responsable de enviar los chunks por la conexión de datos
        y de manejar cancelaciones/timeouts.
        """
        virtual, real = self.secure_resolve(user_root_directory, user_current_directory, file_path)
        if not os.path.exists(real):
            raise FileNotFoundError("File not found")
        if not os.path.isfile(real):
            raise FileNotFoundError("Not a file")

        def _gen():
            with open(real, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

        return _gen()

# Instancia global de FSM
_GLOBAL_FSM = FileSystemManager()

