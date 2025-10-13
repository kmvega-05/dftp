class ClientSession:
    def __init__(self, client_address=None):
        self.client_address = client_address
        self.username = None
        self.authenticated = False 
        self.current_directory = "/"
        self.data_socket = None           # Socket de datos
        self.data_port = None             # Puerto para conexión de datos
        self.pasv_mode = False            # Modo PASV activo
        self.rename_from_path = None 
    
    def set_username(self, username):
        """Establece el nombre de usuario y limpia el estado de la sesión"""
        # Reiniciar la sesión manteniendo client_address
        self.reset_session()
        self.username = username
        print(f"Username set to: {username}")
    
    def authenticate(self):
        """Marca el usuario como autenticado"""
        self.authenticated = True
        print(f"User {self.username} authenticated successfully")
    
    def is_authenticated(self):
        """Verifica si el cliente está autenticado"""
        return self.authenticated
    
    def get_current_directory(self):
        """Obtiene el directorio actual"""
        return self.current_directory
    
    def set_rename_from(self, path):
        """Establece el path para renombrar (RNFR)"""
        self.rename_from_path = path
    
    def get_rename_from(self):
        """Obtiene el path para renombrar"""
        return self.rename_from_path
    
    def clear_rename_from(self):
        """Limpia el estado de renombrar"""
        self.rename_from_path = None
    
    def reset_session(self, client_address=None):
        """Reinicializa toda la sesión (comando REIN)"""
        # Limpiar conexiones de datos antes del reinicio
        self.cleanup_pasv()
        
        # Determinar qué client_address usar
        address_to_use = client_address if client_address is not None else self.client_address
        
        # Reinicializar todos los atributos usando __init__
        self.__init__(client_address=address_to_use)
        
        print(f"Session reset for {self.client_address}")
    
    def cleanup_pasv(self):
        """Limpia el estado PASV después de su uso"""
        if self.data_socket:
            try:
                self.data_socket.close()
                print("Data socket closed")
            except Exception as e:
                print(f"Error closing data socket: {e}")
        
        self.data_socket = None
        self.data_port = None
        self.pasv_mode = False
        print("PASV state cleaned up")
 
    def __str__(self):
        return f"ClientSession(addr={self.client_address}, user={self.username}, auth={self.authenticated})"