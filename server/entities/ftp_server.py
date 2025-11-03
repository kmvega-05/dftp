import socket
import threading
import logging
import importlib
import os
from typing import Callable
from entities.client_session import ClientSession
from entities.command import Command

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def _load_command_handlers():
    """Carga handlers desde el directorio `commands`. """
    handlers = {}
    commands_path = os.path.join(os.path.dirname(__file__), '..', 'commands')

    for filename in os.listdir(commands_path):
        if not filename.endswith('.py'):
            continue

        name = filename[:-3]
        command_name = name.upper()
        module = None

        for prefix in ('server.commands', 'commands'):
            try:
                modname = f"{prefix}.{name}"
                module = importlib.import_module(modname)
                break
            except Exception:
                module = None

        if module is None:
            module_path = os.path.join(commands_path, filename)
            try:
                spec = importlib.util.spec_from_file_location(f"commands.{name}", module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            except Exception as e:
                print(f"Error loading command {command_name}: {e}")
                continue

        handler_func = getattr(module, f'handle_{name}', None) or getattr(module, 'handle', None)
        if handler_func:
            handlers[command_name] = handler_func
            print(f"Loaded command: {command_name}")
        else:
            print(f"Warning: No handler found for {command_name}")

    return handlers

_COMMAND_HANDLERS = _load_command_handlers()

def start_connection_listener(host: str = '0.0.0.0', port: int = 2121, backlog: int = 5, on_client: Callable = None):
    """Punto de entrada para aceptar conexiones y lanzar handlers de cliente.

    Carga los handlers aquí y los pasa a cada `on_client` que se ejecute en
    un hilo separado.
    """

    if on_client is None:
        on_client = client_handler

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(backlog)
    logger.info("FTP connection listener started on %s:%d", host, port)

    try:
        while True:
            try:
                client_sock, client_addr = server_sock.accept()

            except KeyboardInterrupt:
                logger.info("Listener interrupted by user")
                break

            except Exception as e:
                logger.exception("Error accepting connection: %s", e)
                continue

            logger.info("Accepted connection from %s", client_addr)
            t = threading.Thread(target=on_client, args=(client_sock, client_addr), daemon=True)
            t.start()

    finally:
        try:
            server_sock.close()
        except Exception:
            pass

        logger.info("Connection listener stopped")


def client_handler(client_socket: socket.socket, client_address):
    """Crear sesión y ejecutar dispatcher para el cliente."""
    logger.info("Handling new client %s", client_address)
    session = ClientSession(client_address=client_address)

    try:
        session.send_response(client_socket, 220, "Service ready")
        command_dispatcher(client_socket, client_address, session)

    except Exception:
        logger.exception("Error while handling client %s", client_address)

    finally:
        try:
            client_socket.close()
        except Exception:
            logger.exception("Error closing client socket in handler for %s", client_address)

        try:
            session.cleanup_pasv()
        except Exception:
            logger.exception("Error cleaning PASV in handler for %s", client_address)


def command_dispatcher(client_socket: socket.socket, client_address, session: ClientSession):
    """Leer la conexión de control, parsear líneas y despachar handlers."""
    logger.info("Starting command_dispatcher for %s", client_address)
    buf = ""

    try:
        for raw_chunk in recv_chunks(client_socket, chunk_size=4096):
            buf += raw_chunk.decode('utf-8', errors='replace')

            while '\r\n' in buf:
                line, buf = buf.split('\r\n', 1)
                line = line.strip()

                if not line:
                    continue

                try:
                    command = Command(line)
                    logger.info("Received command from %s: %s", client_address, command)
                    handler = _COMMAND_HANDLERS.get(command.get_name())

                    if handler:
                        t = threading.Thread(target=handler, args=(command, client_socket, session), daemon=True)
                        t.start()

                        if session.can_close():
                            logger.info("Closing control connection for %s after pending QUIT", client_address)
                            return

                    else:
                        session.send_response(client_socket, 500, f"Command '{command.get_name()}' not recognized")

                except Exception:
                    logger.exception("Error handling command from %s: %s", client_address, line)

        logger.info("Client %s closed the connection", client_address)
        return

    except Exception:
        logger.exception("Error in command dispatcher for %s", client_address)

    finally:
        session.cleanup_pasv()
        client_socket.close()

    logger.info("Command dispatcher stopped for %s", client_address)


def recv_chunks(sock: socket.socket, chunk_size: int = 65536):
    """Generador que devuelve chunks de bytes desde `sock` hasta EOF."""
    try:
        while True:
            chunk = sock.recv(chunk_size)

            if not chunk:
                break

            yield chunk

    except Exception as e:
        logger.debug("recv_chunks: socket read interrupted: %s", e)
        return


__all__ = [
    'start_conn_listener',
    'client_handler',
]
