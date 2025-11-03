import socket
from entities.file_system_manager import _GLOBAL_FSM as fs_manager, SecurityError

def sock_reader(sock, chunk_size=65536):
    """Generador que lee del socket en chunks y los devuelve.

    Se usa por store_stream para hacer streaming sin guardar todo en memoria.
    """
    try:
        while True:
            data = sock.recv(chunk_size)
            if not data:
                break
            yield data
    finally:
        return

class TransferObj:
    """Wrapper mínimo para registrar una transferencia activa en la sesión.

    Exponemos `cancel()` para que la sesión pueda abortar la transferencia.
    """
    def __init__(self, sock):
        self.data_socket = sock

    def cancel(self):
        try:
            # intentar shutdown antes de close para despertar posibles recv bloqueados
            try:
                self.data_socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            self.data_socket.close()
        except Exception:
            pass


def handle_stor(command, client_socket, client_session):
    """Maneja comando STOR - almacena un archivo recibido del cliente mediante data connection."""

    # 1. Validación de sesión y argumentos
    if not client_session.is_authenticated():
        client_session.send_response(client_socket, 530, "Not logged in")
        return

    if not command.require_args(1):
        client_session.send_response(client_socket, 501, "Syntax error in parameters")
        return

    # 2. Validar modo PASV y socket de datos
    data_socket, _ = client_session.get_pasv_info()
    if not data_socket:
        client_session.send_response(client_socket, 425, "Use PASV first")
        return

    filename = command.get_arg(0)
    user_root = client_session.root_directory

    # 3. Esperar conexión de datos
    try:
        data_conn, _ = data_socket.accept()
    except socket.error:
        client_session.send_response(client_socket, 425, "Can't open data connection")
        client_session.cleanup_pasv()
        return

    transfer = TransferObj(data_conn)
    tid = client_session.start_transfer(transfer)

    try:
        client_session.send_response(client_socket, 150, f"Opening data connection for {filename}")

        success, message = fs_manager.store_stream(user_root, client_session.current_directory, filename, sock_reader(data_conn))

        try:
            data_conn.close()
        except Exception:
            pass

        if success:
            client_session.send_response(client_socket, 226, message)
        else:
            client_session.send_response(client_socket, 550, message)

    except SecurityError as e:
        client_session.send_response(client_socket, 550, str(e))
    except Exception:
        client_session.send_response(client_socket, 450, "Requested file action not taken")
    finally:
        client_session.finish_transfer(tid)
        client_session.cleanup_pasv()
