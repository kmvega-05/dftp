import os
import time
import posixpath
import uuid


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

def get_user_root_directory(username):
    """Obtiene el directorio raíz personal de un usuario"""
    user_dir = os.path.join(BASE_DIRECTORY, username)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    return user_dir

# =============================================================================
# PATH RESOLUTION
# =============================================================================

def secure_path_resolution(user_root_directory, user_current_directory, requested_path):
    """
    Resuelve y valida una ruta de forma segura.
    
    Returns:
        str: Ruta real del filesystem validada
    """
    # 1. Resolver la ruta virtual (lo que el usuario ve)
    virtual_path = resolve_ftp_path(user_current_directory, requested_path)
    
    # 2. Convertir a ruta real
    real_path = get_real_filesystem_path(user_root_directory, virtual_path)
    
    # 3. Validar seguridad
    validate_path_within_root(user_root_directory, real_path)

    return virtual_path

def resolve_ftp_path(user_current_directory, requested_path):
    """
    Resuelve una ruta FTP a una ruta virtual del usuario.
    No incluye el filesystem real.
    
    Returns:
        str: Ruta virtual resuelta (ej: '/folder' o '/current/folder')
    """
    if requested_path.startswith('/'):
        # Path absoluto: relativo al root virtual del usuario
        return posixpath.normpath(requested_path)
    else:
        # Path relativo: relativo al directorio actual virtual
        return posixpath.normpath(posixpath.join(user_current_directory, requested_path))

def get_real_filesystem_path(user_root_directory, virtual_path):
    """
    Convierte una ruta virtual a una ruta real del filesystem.
    
    Returns:
        str: Ruta real del filesystem
    """
    # Eliminar el '/' inicial y unir con el root del usuario
    clean_path = virtual_path.lstrip('/')
    real_path = os.path.join(user_root_directory, clean_path)
    return os.path.normpath(real_path)

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
        virtual_path = secure_path_resolution(user_root_directory, user_current_directory, path)
        real_path = get_real_filesystem_path(user_root_directory, virtual_path)
        return os.path.isdir(real_path)
    except SecurityError:
        return False
    except Exception:
        return False

def file_exists(user_root_directory, user_current_directory, path):
    """Verifica si un archivo existe"""
    try:
        virtual_path = secure_path_resolution(user_root_directory, user_current_directory, path)
        real_path = get_real_filesystem_path(user_root_directory, virtual_path)
        return os.path.isfile(real_path)
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
    Retorna rutas virtuales.
    """
    try:
        virtual_path = secure_path_resolution(user_root_directory, user_current_directory, path)
        real_path = get_real_filesystem_path(user_root_directory, virtual_path)
        
        if not os.path.exists(real_path):
            return None
        
        stat = os.stat(real_path)
        
        # Obtener ruta virtual (lo que el usuario ve)
        virtual_path = resolve_ftp_path(user_current_directory, path)
        name = os.path.basename(virtual_path)
        
        # Determinar tipo
        if os.path.isdir(real_path):
            file_type = "directory"
        elif os.path.isfile(real_path):
            file_type = "file"
        else:
            file_type = "other"
        
        return {
            'name': name,
            'path': virtual_path,
            'type': file_type,
            'size': stat.st_size,
            'permissions': stat.st_mode,
            'modified': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
            'accessed': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_atime)),
        }
        
    except (SecurityError, OSError):
        return None

def list_directory_detailed(user_root_directory, user_current_directory, path="."):
    """
    Lista contenido con información completa (para LIST).
    Retorna string formateado simple.
    """
    try:
        virtual_path = secure_path_resolution(user_root_directory, user_current_directory, path)
        real_path = get_real_filesystem_path(user_root_directory, virtual_path)
        
        if not os.path.isdir(real_path):
            return None
        
        entries = []
        for entry_name in os.listdir(real_path):
            # Para cada archivo en el filesystem real, crear su ruta virtual
            virtual_entry_path = resolve_ftp_path(user_current_directory, 
                                                posixpath.join(path, entry_name))
            file_info = get_file_info(user_root_directory, user_current_directory, 
                                    virtual_entry_path)
            if file_info:
                entries.append(file_info)
        
        # Usar la función de formateo
        return format_simple_listing(entries)
        
    except (SecurityError, OSError):
        return None

def list_directory_names(user_root_directory, user_current_directory, path="."):
    """
    Lista solo nombres de archivos/directorios (para NLST).
    
    Returns:
        List[str] con nombres de cada elemento
    """
    try:
        virtual_path = secure_path_resolution(user_root_directory, user_current_directory, path)
        real_path = get_real_filesystem_path(user_root_directory, virtual_path)
        
        if not os.path.isdir(real_path):
            return []
        
        return os.listdir(real_path)
        
    except (SecurityError, OSError):
        return []

def format_simple_listing(directory_entries):
    """
    Formatea una lista de entries a string simple.
    
    Args:
        directory_entries: Lista de diccionarios de get_file_info
    
    Returns:
        str: Listado formateado simple
    """
    if not directory_entries:
        return ""
    
    listing = ""
    for file_info in directory_entries:
        type_indicator = "d" if file_info['type'] == 'directory' else "-"
        size = file_info['size']
        modified = file_info['modified']
        name = file_info['name']
        
        listing += f"{type_indicator} {size:>8} {modified} {name}\r\n"
    
    return listing
    
# ==============================================================================================
# FILE AND DIRECTORY OPERATIONS
# ==============================================================================================

def change_directory(user_root_directory, user_current_directory, new_path):
    """Cambia el directorio actual"""
    try:
        virtual_path = secure_path_resolution(user_root_directory, user_current_directory, new_path)
        real_path = get_real_filesystem_path(user_root_directory, virtual_path)
        
        if os.path.isdir(real_path):
            # Resolver la nueva ruta virtual (lo que el usuario debe ver)
            virtual_path = resolve_ftp_path(user_current_directory, new_path)
            return virtual_path
        return None
        
    except SecurityError:
        # Si hay intento de path traversal, retornar root
        return "/"
    except Exception as e:
        print(f"Error changing directory: {e}")
        return None
    
def create_directory(user_root_directory, user_current_directory, new_dir_path):
    """Crea un nuevo directorio de forma segura"""
    try:
        virtual_path = secure_path_resolution(user_root_directory, user_current_directory, new_dir_path)
        real_path = get_real_filesystem_path(user_root_directory, virtual_path)
        
        # Verificar si el directorio ya existe
        if os.path.exists(real_path):
            return False, "Directory already exists"
        
        # Crear el directorio
        os.makedirs(real_path)
        return True, f'"{new_dir_path}" directory created'
        
    except SecurityError:
        return False, "Path traversal attempt detected"
    except Exception as e:
        print(f"Error creating directory: {e}")
        return False, "Failed to create directory"

def remove_directory(user_root_directory, user_current_directory, dir_path):
    """Elimina un directorio de forma segura"""
    try:
        virtual_path = secure_path_resolution(user_root_directory, user_current_directory, dir_path)
        real_path = get_real_filesystem_path(user_root_directory, virtual_path)
        
        # Verificar si el directorio existe
        if not os.path.exists(real_path):
            return False, "Directory does not exist"
        
        # Verificar que es un directorio
        if not os.path.isdir(real_path):
            return False, "Not a directory"
        
        # Verificar que el directorio esté vacío
        if len(os.listdir(real_path)) > 0:
            return False, "Directory not empty"
        
        # Eliminar el directorio
        os.rmdir(real_path)
        return True, f'"{dir_path}" directory removed"'
        
    except SecurityError:
        return False, "Path traversal attempt detected"
    except Exception as e:
        print(f"Error removing directory: {e}")
        return False, "Failed to remove directory"

def delete_file(user_root_directory, user_current_directory, file_path):
    """Elimina un archivo de forma segura"""
    try:
        virtual_path = secure_path_resolution(user_root_directory, user_current_directory, file_path)
        real_path = get_real_filesystem_path(user_root_directory, virtual_path)
        
        # Verificar si el archivo existe
        if not os.path.exists(real_path):
            return False, "File not found"
        
        # Verificar que es un archivo (no un directorio)
        if not os.path.isfile(real_path):
            return False, "Not a file"
        
        # Eliminar el archivo
        os.remove(real_path)
        return True, f'"{file_path}" file deleted'
        
    except SecurityError:
        return False, "Path traversal attempt detected"
    except Exception as e:
        print(f"Error deleting file: {e}")
        return False, "Failed to delete file"

def rename_path(user_root_directory, user_current_directory, old_path, new_path):
    """Renombra un archivo o directorio de forma segura"""
    try:
        old_virtual_path = secure_path_resolution(user_root_directory, user_current_directory, old_path)
        old_real_path = get_real_filesystem_path(user_root_directory, old_virtual_path)

        new_virtual_path = secure_path_resolution(user_root_directory, user_current_directory, new_path)
        new_real_path = get_real_filesystem_path(user_root_directory, new_virtual_path)
        
        # Verificar que el origen existe
        if not os.path.exists(old_real_path):
            return False, "Source path not found"
        
        # Verificar que el destino no existe
        if os.path.exists(new_real_path):
            return False, "Destination path already exists"
        
        # Renombrar
        os.rename(old_real_path, new_real_path)
        return True, f'"{old_path}" renamed to "{new_path}"'
        
    except SecurityError:
        return False, "Path traversal attempt detected"
    except Exception as e:
        print(f"Error renaming path: {e}")
        return False, "Failed to rename"
    
def generate_unique_filename(user_root_directory, user_current_directory, original_filename):
    """Genera un nombre único para un archivo"""
    try:
        # Extraer extensión si existe
        name, ext = os.path.splitext(original_filename)
        
        # Generar nombre único
        unique_name = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
        
        # Verificar que no exista (poco probable pero bueno)
        virtual_path = secure_path_resolution(user_root_directory, user_current_directory, unique_name)
        real_path = get_real_filesystem_path(user_root_directory, virtual_path)
        
        counter = 1
        while os.path.exists(real_path):
            unique_name = f"{name}_{uuid.uuid4().hex[:8]}_{counter}{ext}"
            virtual_path = secure_path_resolution(user_root_directory, user_current_directory, unique_name)
            real_path = get_real_filesystem_path(user_root_directory, virtual_path)
            counter += 1
        
        return unique_name
        
    except Exception as e:
        print(f"Error generating unique filename: {e}")
        return f"file_{uuid.uuid4().hex[:8]}" 

def store_file_optimized(user_root_directory, user_current_directory, file_path, data_conn, max_buffer_size=10485760):  # 10MB
    """Almacena archivo usando buffer pequeño o stream según tamaño"""
    try:
        virtual_path = secure_path_resolution(user_root_directory, user_current_directory, file_path)
        real_path = get_real_filesystem_path(user_root_directory, virtual_path)
        
        # Crear directorio padre
        parent_dir = os.path.dirname(real_path)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        
        # Buffer para los primeros bytes (para decidir el enfoque)
        initial_buffer = b""
        total_received = 0
        use_stream = False
        
        with open(real_path, 'wb') as f:
            data_conn.settimeout(30.0)
            
            while True:
                chunk = data_conn.recv(65536)  # 64KB chunks
                if not chunk:
                    break
                
                total_received += len(chunk)
                
                if not use_stream:
                    # Si aún estamos en modo buffer
                    initial_buffer += chunk
                    
                    if len(initial_buffer) > max_buffer_size:
                        # Cambiar a stream - archivo grande
                        print(f"File exceeds {max_buffer_size} bytes, switching to stream mode")
                        f.write(initial_buffer)  # Escribe lo acumulado
                        initial_buffer = None  # Liberar memoria
                        use_stream = True
                else:
                    # Modo stream - escribir directamente
                    f.write(chunk)
                
                print(f"Received {total_received} bytes...")
            
            # Si terminó en modo buffer, escribir todo
            if not use_stream and initial_buffer:
                f.write(initial_buffer)
        
        return True, f'"{file_path}" file stored successfully ({total_received} bytes)'
        
    except SecurityError:
        return False, "Path traversal attempt detected"
    
    except Exception as e:
        print(f"Error storing file: {e}")
        # Intentar limpiar archivo parcial
        try:
            if os.path.exists(real_path):
                os.remove(real_path)
        except:
            pass
        return False, "Failed to store file"

def retrieve_file(user_root_directory, user_current_directory, file_path, data_conn, chunk_size=65536):
    """Recupera y envía un archivo por streaming"""
    try:
        virtual_path = secure_path_resolution(user_root_directory, user_current_directory, file_path)
        real_path = get_real_filesystem_path(user_root_directory, virtual_path)
        
        if not os.path.exists(real_path):
            return False, "File not found"
        
        if not os.path.isfile(real_path):
            return False, "Not a file"
        
        file_size = os.path.getsize(real_path)
        
        # Streaming: leer y enviar por chunks
        with open(real_path, 'rb') as f:
            total_sent = 0
            while True:
                chunk = f.read(chunk_size)  # Lee chunk
                if not chunk:
                    break
                data_conn.send(chunk)  # Envía chunk
                total_sent += len(chunk)
                # Opcional: mostrar progreso para archivos muy grandes
                if file_size > 10485760:  # > 10MB
                    print(f"RETR progress: {total_sent}/{file_size} bytes")
        
        return True, f"Transfer complete ({total_sent} bytes)"
        
    except SecurityError:
        return False, "Path traversal attempt detected"
    except Exception as e:
        print(f"Error retrieving file: {e}")
        return False, "Failed to retrieve file"