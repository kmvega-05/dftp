import socket
import threading
import importlib
import os
from entities.command import Command
from entities.client_session import ClientSession
from entities.file_system import ensure_base_directory 

class FTPServer:
    def __init__(self, host='localhost', port=2121):
        self.host = host
        self.port = port
        self.server_socket = None
        self.command_handlers = self._load_command_handlers()
        ensure_base_directory()
            
    def _load_command_handlers(self):
        """Carga automáticamente todos los handlers de comandos"""
        handlers = {}
        commands_path = os.path.join(os.path.dirname(__file__), '..', 'commands')
        
        for filename in os.listdir(commands_path):
            if filename.endswith('.py'):
                command_name = filename[:-3].upper()  # USER, PASS, etc.
                module_name = f"commands.{filename[:-3]}"
                
                try:
                    module = importlib.import_module(module_name)
                    handler_func = getattr(module, f'handle_{filename[:-3]}', None)
                    
                    if handler_func:
                        handlers[command_name] = handler_func
                        print(f"Loaded command: {command_name}")
                    else:
                        print(f"Warning: No handler found for {command_name}")
                        
                except ImportError as e:
                    print(f"Error loading command {command_name}: {e}")
        
        return handlers

    def send_response(self, client_socket, response_code, response_message):
        """Envia una respuesta FTP al cliente a traves del socket de control"""
        response = f"{response_code} {response_message}\r\n"
        client_socket.send(response.encode('utf-8'))
        # Log
        print(f"Respuesta Enviada : {response}")

    def start_server(self):
        """Inicia el servidor FTP en el puerto especificado"""
        try:
            self.setup_server_socket()
            
            while True:
                # Aceptar conexiones entrantes
                client_socket, client_address = self.server_socket.accept()
                print(f"Nueva conexion desde {client_address}")
                
                # Manejar cada cliente en un hilo separado
                self.create_client_thread(client_socket, client_address)
                    
        except Exception as e:
            print(f"Error iniciando servidor: {e}")

        finally:
            if self.server_socket:
                self.server_socket.close()

    def setup_server_socket(self):
        """Crea y configura el socket del servidor"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)

        # Logs
        print(f"Servidor FTP iniciado en {self.host}:{self.port}")
        print("Esperando conexiones...")
    
    def create_client_thread(self, client_socket, client_address):
        """Crea y configura un hilo para manejar un cliente"""
        client_thread = threading.Thread(
            target=self.handle_client,
            args=(client_socket, client_address)
        )

        client_thread.daemon = True
        client_thread.start()
        print(f"Log : Hilo creado para cliente {client_address}")
    
    def handle_client(self, client_socket, client_address):
        """Maneja la comunicacion con un cliente FTP"""
        # Crear sesión para este cliente
        client_session = ClientSession(client_address)
        
        try:
            # Enviar mensaje de bienvenida usando send_response
            self.send_response(client_socket, 220, "Welcome to KM FTP Server")
        
            # Manejar los comandos FTP pasando la sesión
            self.dispatch_commands(client_socket, client_address, client_session)
        
        except Exception as e:
            print(f"Error manejando cliente {client_address}: {e}")
        finally:
            client_socket.close()
            print(f"Conexion cerrada con {client_address}")
            print(f"Sesion finalizada: {client_session}")

    
    def dispatch_commands(self, client_socket, client_address, client_session):
        """Maneja y despacha los comandos FTP del cliente"""
        try:
            while True:
                data = client_socket.recv(1024).decode('utf-8').strip()
                if not data:
                    break
            
                print(f"Comando recibido de {client_address}: {data}")
                print(f"Estado sesion: {client_session}")
        
                # Parsear el comando
                command = Command(data)
                print(f"Comando parseado: {command}")
        
                # Despachar al manejador correspondiente
                handler = self.command_handlers.get(command.name, handle_unknown)
                handler(command, client_socket, self, client_session)

                if command.get_name() == "QUIT" :
                    print("QUIT command received, closing connection")
                    break
        
        except Exception as e:
            print(f"Error en comunicación con {client_address}: {e}")
        finally:
            # Limpiar PASV al desconectar el cliente
            if client_session.pasv_mode:
                client_session.cleanup_pasv

def handle_unknown(command, client_socket, server, client_session):
    """Maneja comandos desconocidos"""
    server.send_response(client_socket, 500, f"Command '{command.get_name()}' not recognized")