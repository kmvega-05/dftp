import os
import time
import posixpath

# Configuración
BASE_DIRECTORY = "/tmp/ftp_root"

class SecurityError(Exception):
    """Excepción para errores de seguridad"""
    pass

def ensure_base_directory():
    """Asegura que el directorio base exista"""
    if not os.path.exists(BASE_DIRECTORY):
        os.makedirs(BASE_DIRECTORY)
        print(f"Created base directory: {BASE_DIRECTORY}")

def get_user_root_directory(username):
    """Obtiene el directorio raíz personal de un usuario"""
    ensure_base_directory()
    user_dir = os.path.join(BASE_DIRECTORY, username)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    return user_dir

def sanitize_path(user_directory, requested_path):
    """Sanitiza una ruta para prevenir directory traversal"""
    if requested_path.startswith('/'):
        clean_path = posixpath.normpath(requested_path)
    else:
        clean_path = posixpath.normpath(posixpath.join('/', requested_path))
    
    full_path = os.path.join(user_directory, clean_path.lstrip('/'))
    full_path = os.path.normpath(full_path)
    
    if not full_path.startswith(os.path.abspath(user_directory)):
        raise SecurityError("Path traversal attempt detected")
    
    return full_path

def directory_exists(user_directory, path):
    """Verifica si un directorio existe"""
    try:
        full_path = sanitize_path(user_directory, path)
        return os.path.isdir(full_path)
    except SecurityError:
        return False
    except Exception:
        return False

def file_exists(user_directory, path):
    """Verifica si un archivo existe"""
    try:
        full_path = sanitize_path(user_directory, path)
        return os.path.isfile(full_path)
    except SecurityError:
        return False
    except Exception:
        return False

def change_directory(user_directory, new_path):
    """Cambia el directorio actual"""
    try:
        full_path = sanitize_path(user_directory, new_path)
        if os.path.isdir(full_path):
            relative_path = os.path.relpath(full_path, user_directory)
            if relative_path == '.':
                return '/'
            return '/' + relative_path
        return None
    except SecurityError:
        return None
    except Exception as e:
        print(f"Error changing directory: {e}")
        return None

def list_directory(user_directory, path="."):
    """Lista el contenido de un directorio"""
    try:
        full_path = sanitize_path(user_directory, path)
        if not os.path.isdir(full_path):
            return None
        
        entries = os.listdir(full_path)
        return entries
    except SecurityError:
        return None
    except Exception as e:
        print(f"Error listing directory: {e}")
        return None

def generate_directory_listing(user_root, current_directory):
    """Genera listado al estilo UNIX dentro del sandbox del usuario"""
    try:
        entries = list_directory(user_root, current_directory)
        
        if entries is None:
            return "total 0\r\n"
        
        listing = ""
        for entry in entries:
            try:
                full_path = sanitize_path(user_root, os.path.join(current_directory, entry))
                stat = os.stat(full_path)
                
                permissions = "drwxr-xr-x" if os.path.isdir(full_path) else "-rw-r--r--"
                nlinks = stat.st_nlink
                user = "user"
                group = "group"
                size = stat.st_size
                mtime = time.strftime("%b %d %H:%M", time.gmtime(stat.st_mtime))
                
                listing += f"{permissions} {nlinks} {user} {group} {size:8} {mtime} {entry}\r\n"
            
            except Exception as e:
                listing += f"??????????   1 user group        0 Jan 01  1970 {entry}\r\n"
        
        return listing
        
    except Exception as e:
        print(f"Error generating directory listing: {e}")
        return "total 0\r\n"

def generate_name_listing(user_root, current_directory):
    """Genera lista de solo nombres de archivos (para NLST)"""
    try:
        entries = list_directory(user_root, current_directory)
        
        if entries is None:
            return ""
        
        # Solo nombres, uno por línea
        name_list = ""
        for entry in entries:
            name_list += f"{entry}\r\n"
        
        return name_list
        
    except Exception as e:
        print(f"Error generating name listing: {e}")
        return ""
    
def create_directory(user_directory, new_dir_path):
    """Crea un nuevo directorio de forma segura"""
    try:
        full_path = sanitize_path(user_directory, new_dir_path)
        
        # Verificar si el directorio ya existe
        if os.path.exists(full_path):
            return False, "Directory already exists"
        
        # Crear el directorio
        os.makedirs(full_path)
        return True, f'"{new_dir_path}" directory created'
        
    except SecurityError:
        return False, "Path traversal attempt detected"
    except Exception as e:
        print(f"Error creating directory: {e}")
        return False, "Failed to create directory"

def remove_directory(user_directory, dir_path):
    """Elimina un directorio de forma segura"""
    try:
        full_path = sanitize_path(user_directory, dir_path)
        
        # Verificar si el directorio existe
        if not os.path.exists(full_path):
            return False, "Directory does not exist"
        
        # Verificar que es un directorio
        if not os.path.isdir(full_path):
            return False, "Not a directory"
        
        # Verificar que el directorio esté vacío
        if len(os.listdir(full_path)) > 0:
            return False, "Directory not empty"
        
        # Eliminar el directorio
        os.rmdir(full_path)
        return True, f'"{dir_path}" directory removed'
        
    except SecurityError:
        return False, "Path traversal attempt detected"
    except Exception as e:
        print(f"Error removing directory: {e}")
        return False, "Failed to remove directory"

def store_file_optimized(user_directory, file_path, data_conn, max_buffer_size=10485760):  # 10MB
    """Almacena archivo usando buffer pequeño o stream según tamaño"""
    try:
        full_path = sanitize_path(user_directory, file_path)
        
        # Crear directorio padre
        parent_dir = os.path.dirname(full_path)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        
        # Buffer para los primeros bytes (para decidir el enfoque)
        initial_buffer = b""
        total_received = 0
        use_stream = False
        
        with open(full_path, 'wb') as f:
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
            if os.path.exists(full_path):
                os.remove(full_path)
        except:
            pass
        return False, "Failed to store file"

import uuid

def generate_unique_filename(user_directory, original_filename):
    """Genera un nombre único para un archivo"""
    try:
        # Extraer extensión si existe
        name, ext = os.path.splitext(original_filename)
        
        # Generar nombre único
        unique_name = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
        
        # Verificar que no exista (poco probable pero bueno)
        full_path = sanitize_path(user_directory, unique_name)
        counter = 1
        while os.path.exists(full_path):
            unique_name = f"{name}_{uuid.uuid4().hex[:8]}_{counter}{ext}"
            full_path = sanitize_path(user_directory, unique_name)
            counter += 1
        
        return unique_name
        
    except Exception as e:
        print(f"Error generating unique filename: {e}")
        return f"file_{uuid.uuid4().hex[:8]}"

def retrieve_file(user_directory, file_path, data_conn, chunk_size=65536):
    """Recupera y envía un archivo por streaming"""
    try:
        full_path = sanitize_path(user_directory, file_path)
        
        if not os.path.exists(full_path):
            return False, "File not found"
        
        if not os.path.isfile(full_path):
            return False, "Not a file"
        
        file_size = os.path.getsize(full_path)
        
        # Streaming: leer y enviar por chunks
        with open(full_path, 'rb') as f:
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

def delete_file(user_directory, file_path):
    """Elimina un archivo de forma segura"""
    try:
        full_path = sanitize_path(user_directory, file_path)
        
        # Verificar si el archivo existe
        if not os.path.exists(full_path):
            return False, "File not found"
        
        # Verificar que es un archivo (no un directorio)
        if not os.path.isfile(full_path):
            return False, "Not a file"
        
        # Eliminar el archivo
        os.remove(full_path)
        return True, f'"{file_path}" file deleted'
        
    except SecurityError:
        return False, "Path traversal attempt detected"
    except Exception as e:
        print(f"Error deleting file: {e}")
        return False, "Failed to delete file"

def rename_path(user_directory, old_path, new_path):
    """Renombra un archivo o directorio de forma segura"""
    try:
        old_full_path = sanitize_path(user_directory, old_path)
        new_full_path = sanitize_path(user_directory, new_path)
        
        # Verificar que el origen existe
        if not os.path.exists(old_full_path):
            return False, "Source path not found"
        
        # Verificar que el destino no existe
        if os.path.exists(new_full_path):
            return False, "Destination path already exists"
        
        # Renombrar
        os.rename(old_full_path, new_full_path)
        return True, f'"{old_path}" renamed to "{new_path}"'
        
    except SecurityError:
        return False, "Path traversal attempt detected"
    except Exception as e:
        print(f"Error renaming path: {e}")
        return False, "Failed to rename"

def get_file_status(user_directory, file_path):
    """Obtiene información detallada de un archivo/directorio"""
    try:
        full_path = sanitize_path(user_directory, file_path)
        
        if not os.path.exists(full_path):
            return None, "File or directory not found"
        
        stat = os.stat(full_path)
        
        # Determinar tipo
        if os.path.isdir(full_path):
            file_type = "directory"
        elif os.path.isfile(full_path):
            file_type = "file"
        else:
            file_type = "other"
        
        # Información detallada
        status_info = {
            'type': file_type,
            'size': stat.st_size,
            'permissions': stat.st_mode,
            'modified': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
            'accessed': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_atime)),
        }
        
        return status_info, f'Status of {file_path}'
        
    except SecurityError:
        return None, "Path traversal attempt detected"
    except Exception as e:
        print(f"Error getting file status: {e}")
        return None, "Failed to get file status"

