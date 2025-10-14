import os
import time
import posixpath

BASE_DIRECTORY = "/tmp/ftp_root"

class SecurityError(Exception):
    """Excepción para errores de seguridad"""
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================

def ensure_base_directory():
    """Asegura que el directorio base exista"""
    if not os.path.exists(BASE_DIRECTORY):
        os.makedirs(BASE_DIRECTORY)
        print(f"Created base directory: {BASE_DIRECTORY}")

# =============================================================================
# PATH RESOLUTION
# =============================================================================
def get_user_root_directory(username):
    """Obtiene el directorio raíz personal de un usuario"""
    user_dir = os.path.join(BASE_DIRECTORY, username)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    return user_dir

def secure_path_resolution(user_root_directory, user_current_directory, requested_path):
    """
    Resuelve y valida una ruta de forma segura.

    Args:
        user_root_directory: Directorio raíz del usuario
        user_current_directory: Directorio actual del usuario (relativo al root)
        requested_path: Ruta solicitada por el cliente FTP
    
    Returns:
        str: Ruta del sistema de archivos resuelta normalizada y validando que se encuentre dentro del directorio
            root del usuario.
    """
    resolved = resolve_path(user_root_directory, user_current_directory, requested_path)
    return validate_path_within_root(user_root_directory, resolved)

def resolve_path(user_root_directory, user_current_directory, requested_path):
    """
    Resuelve una ruta FTP a una ruta del sistema de archivos.
    
    Args:
        user_root_directory: Directorio raíz del usuario
        user_current_directory: Directorio actual del usuario (relativo al root)
        requested_path: Ruta solicitada por el cliente FTP
    
    Returns:
        str: Ruta del sistema de archivos resuelta
    """
    if requested_path.startswith('/'):
        # Path absoluto: relativo al root del usuario
        return os.path.join(user_root_directory, requested_path.lstrip('/'))
    else:
        # Path relativo: relativo al directorio actual del usuario
        current_full_path = os.path.join(user_root_directory, user_current_directory.lstrip('/'))
        return os.path.join(current_full_path, requested_path)
    
def validate_path_within_root(user_root_directory, resolved_path):
    """
    Valida que una ruta esté dentro del directorio raíz del usuario.
    
    Args:
        user_root_directory: Directorio raíz del usuario
        resolved_path: Ruta a validar
    
    Returns:
        str: Ruta normalizada y validada
    
    Raises:
        SecurityError: Si la ruta está fuera del directorio raíz
    """
    # Normalizar la ruta
    normalized_path = os.path.normpath(resolved_path)
    normalized_root = os.path.normpath(user_root_directory)
    
    # Verificar que esté dentro del directorio raíz
    if not normalized_path.startswith(normalized_root):
        raise SecurityError("Path traversal attempt detected")
    
    return normalized_path

# =============================================================================
# FILE SYSTEM QUERIES
# =============================================================================

def directory_exists(user_root_directory, user_current_directory, path):
    """Verifica si un directorio existe"""
    try:
        full_path = secure_path_resolution(user_root_directory, user_current_directory, path)
        return os.path.isdir(full_path)
    except SecurityError:
        return False
    except Exception:
        return False

def file_exists(user_root_directory, user_current_directory, path):
    """Verifica si un archivo existe"""
    try:
        full_path = secure_path_resolution(user_root_directory, user_current_directory, path)
        return os.path.isfile(full_path)
    except SecurityError:
        return False
    except Exception:
        return False
    
# =============================================================================
# DIRECTORY LISTING 
# =============================================================================

def get_file_info(user_root_directory, user_current_directory, path):
    """
    Obtiene información completa de un archivo/directorio.
    
    Returns:
        dict con keys: name, type, size, permissions, modified, accessed
        o None si no existe
    """
    try:
        full_path = secure_path_resolution(user_root_directory, user_current_directory, path)
        
        if not os.path.exists(full_path):
            return None
        
        stat = os.stat(full_path)
        name = os.path.basename(full_path)
        
        # Determinar tipo
        if os.path.isdir(full_path):
            file_type = "directory"
        elif os.path.isfile(full_path):
            file_type = "file"
        else:
            file_type = "other"
        
        return {
            'name': name,
            'type': file_type,
            'size': stat.st_size,
            'permissions': stat.st_mode,
            'modified': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
            'accessed': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_atime)),
            'full_path': full_path
        }
        
    except (SecurityError, OSError):
        return None

def list_directory_detailed(user_root_directory, user_current_directory, path="."):
    """
    Lista contenido con información completa (para LIST).
    
    Returns:
        List[dict] con información de cada elemento del directorio
    """
    try:
        full_path = secure_path_resolution(user_root_directory, user_current_directory, path)
        
        if not os.path.isdir(full_path):
            return []
        
        entries = []
        for entry_name in os.listdir(full_path):
            entry_path = os.path.join(path, entry_name)
            file_info = get_file_info(user_root_directory, user_current_directory, entry_path)
            if file_info:
                entries.append(file_info)
        
        return entries
        
    except (SecurityError, OSError):
        return []

def list_directory_names(user_root_directory, user_current_directory, path="."):
    """
    Lista solo nombres de archivos/directorios (para NLST).
    
    Returns:
        List[str] con nombres de cada elemento
    """
    try:
        full_path = secure_path_resolution(user_root_directory, user_current_directory, path)
        
        if not os.path.isdir(full_path):
            return []
        
        return os.listdir(full_path)
        
    except (SecurityError, OSError):
        return []