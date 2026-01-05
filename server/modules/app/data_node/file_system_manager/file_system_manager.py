import os
import time
import posixpath
import uuid
import tempfile
import threading
from contextlib import contextmanager

BASE_DIRECTORY = "/tmp/ftp_root"


class SecurityError(Exception):
    """Excepción para errores de seguridad (path traversal, escapes, etc.)."""
    pass


class FileLockManager:
    """Administra locks por ruta (in-memory). Previene races locales."""

    def __init__(self):
        self._locks = {}
        self._global_lock = threading.Lock()

    @contextmanager
    def acquire(self, path):
        """Context manager para adquirir un lock sobre un path específico."""
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
    """
    API segura y robusta para operaciones sobre el filesystem.

    Contrato:
    - Todas las rutas externas son virtuales POSIX (empiezan con '/')
    - Todas las validaciones de seguridad ocurren aquí
    - Éxito = no excepción
    - Fallo = excepción semántica clara
    """

    def __init__(self, base_directory=BASE_DIRECTORY):
        self.root_dir = os.path.abspath(base_directory)
        self.lock_mgr = FileLockManager()
        os.makedirs(self.root_dir, exist_ok=True)

    # --------------------------- Namespace --------------------------
    
    def get_namespace(self, namespace):
        """
        Devuelve el directorio raíz del namespace (usuario/bucket/etc.).
        Si no existe, lo crea.
        """
        namespace_path = os.path.join(self.root_dir, namespace)

        # Crear el directorio si no existe
        os.makedirs(namespace_path, exist_ok=True)

        return namespace_path
    # --------------------------- Path utils ---------------------------

    def normalize_virtual_path(self, cwd, path):
        """Normaliza un path virtual POSIX según el directorio actual (cwd)."""
        if path.startswith("/"):
            return posixpath.normpath(path)
        return posixpath.normpath(posixpath.join(cwd, path))

    def virtual_to_real_path(self, root_dir, virtual_path):
        """Convierte un path virtual POSIX a un path real en el filesystem."""
        clean = virtual_path.lstrip("/")
        return os.path.normpath(os.path.join(root_dir, clean))

    def _check_path_within_root(self, root_dir, real_path):
        """Lanza SecurityError si el path real está fuera del root_dir."""
        root_real = os.path.realpath(root_dir)
        path_real = os.path.realpath(real_path)

        try:
            common = os.path.commonpath([root_real, path_real])
        except ValueError:
            raise SecurityError("Path traversal attempt detected")

        if common != root_real:
            raise SecurityError("Path traversal attempt detected")

    def resolve_and_secure_path(self, root_dir, cwd, path):
        """
        Retorna (virtual_path, real_path) validando seguridad.
        """
        virtual = self.normalize_virtual_path(cwd, path)
        real = self.virtual_to_real_path(root_dir, virtual)
        self._check_path_within_root(root_dir, real)
        return virtual, real

    # --------------------------- Validation ---------------------------

    def validate_path(self, root_dir, cwd, path, want="any"):
        """
        Valida la existencia y tipo del path.
        want = "any" | "file" | "dir"
        Retorna (virtual_path, real_path) si válido.
        """
        virtual, real = self.resolve_and_secure_path(root_dir, cwd, path)

        with self.lock_mgr.acquire(real):
            if not os.path.exists(real):
                raise FileNotFoundError("Path not found")

            if want == "any":
                return virtual, real
            if want == "file":
                if os.path.isfile(real):
                    return virtual, real
                raise IsADirectoryError("Not a file")
            if want == "dir":
                if os.path.isdir(real):
                    return virtual, real
                raise NotADirectoryError("Not a directory")

            raise ValueError(f"Invalid want parameter: {want}")

    # --------------------------- Directory ops ---------------------------

    def list_dir(self, root_dir, cwd, path="."):
        """Lista nombres de archivos/directorios en el path dado."""
        _, real = self.validate_path(root_dir, cwd, path, want="dir")
        with self.lock_mgr.acquire(real):
            return os.listdir(real)

    def list_dir_with_stats(self, root_dir, cwd, path="."):
        """Lista el contenido del directorio incluyendo información detallada."""
        _, real = self.validate_path(root_dir, cwd, path, want="dir")
        results = []

        with self.lock_mgr.acquire(real):
            for entry in os.listdir(real):
                vpath = posixpath.join(self.normalize_virtual_path(cwd, path), entry)
                results.append(self.stat(root_dir, cwd, vpath))
        return results

    def stat(self, root_dir, cwd, path):
        """Devuelve un dict con información de un archivo o directorio."""
        virtual, real = self.resolve_and_secure_path(root_dir, cwd, path)
        if not os.path.exists(real):
            return None

        s = os.stat(real)
        return {
            "name": os.path.basename(virtual),
            "path": virtual,
            "size": s.st_size,
            "permissions": s.st_mode,
            "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s.st_mtime)),
            "accessed": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s.st_atime)),
            "is_dir": os.path.isdir(real),
            "is_file": os.path.isfile(real),
        }

    def make_dir(self, root_dir, cwd, path):
        """Crea un directorio nuevo; falla si ya existe."""
        _, real = self.resolve_and_secure_path(root_dir, cwd, path)
        with self.lock_mgr.acquire(real):
            if os.path.exists(real):
                raise FileExistsError("Directory already exists")
            os.makedirs(real)

    def remove_dir(self, root_dir, cwd, path):
        """Elimina un directorio vacío; falla si no existe o tiene contenido."""
        _, real = self.validate_path(root_dir, cwd, path, want="dir")
        with self.lock_mgr.acquire(real):
            if os.listdir(real):
                raise OSError("Directory not empty")
            os.rmdir(real)

    def delete_file(self, root_dir, cwd, path):
        """Elimina un archivo."""
        _, real = self.validate_path(root_dir, cwd, path, want="file")
        with self.lock_mgr.acquire(real):
            os.remove(real)

    def rename_path(self, root_dir, cwd, old_path, new_path):
        """Renombra archivo o directorio."""
        _, old_real = self.resolve_and_secure_path(root_dir, cwd, old_path)
        _, new_real = self.resolve_and_secure_path(root_dir, cwd, new_path)

        # Locking consistente para evitar deadlocks
        lock1, lock2 = (old_real, new_real) if old_real <= new_real else (new_real, old_real)
        with self.lock_mgr.acquire(lock1), self.lock_mgr.acquire(lock2):
            if not os.path.exists(old_real):
                raise FileNotFoundError("Source path not found")
            if os.path.exists(new_real):
                raise FileExistsError("Destination already exists")
            os.rename(old_real, new_real)

    # --------------------------- Stream ops ---------------------------

    def generate_unique_filename(self, root_dir, cwd, original_filename):
        """Genera un nombre único basado en el original."""
        name, ext = os.path.splitext(original_filename)
        for _ in range(10):
            candidate = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
            _, real = self.resolve_and_secure_path(root_dir, cwd, candidate)
            if not os.path.exists(real):
                return candidate
        return f"{name}_{uuid.uuid4().hex[:8]}{ext}"

    def write_stream(self, root_dir, cwd, path, data_iterable, chunk_size=65536):
        """Almacena datos desde un iterable binario en el archivo destino de manera atómica."""
        _, real = self.resolve_and_secure_path(root_dir, cwd, path)
        parent = os.path.dirname(real)
        os.makedirs(parent, exist_ok=True)

        with self.lock_mgr.acquire(real):
            with tempfile.NamedTemporaryFile(dir=parent, delete=False) as tmp:
                tmp_path = tmp.name
                try:
                    for chunk in data_iterable:
                        if chunk:
                            tmp.write(chunk)
                    tmp.flush()
                    os.fsync(tmp.fileno())
                except Exception:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                    raise

            os.replace(tmp_path, real)

    def read_stream(self, root_dir, cwd, path, chunk_size=65536):
        """Retorna un generador que lee un archivo en chunks binarios."""
        _, real = self.resolve_and_secure_path(root_dir, cwd, path)

        if not os.path.exists(real):
            raise FileNotFoundError("File not found")
        if not os.path.isfile(real):
            raise IsADirectoryError("Not a file")

        def _gen():
            with self.lock_mgr.acquire(real):
                with open(real, "rb") as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
        return _gen()
