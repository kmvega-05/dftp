from entities.file_system_manager import _GLOBAL_FSM as fs_manager, SecurityError
import socket

def sock_reader(sock, chunk_size=65536):
    try:
        while True:
            chunk = sock.recv(chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        return


class TransferObj:
    def __init__(self, sock):
        self.data_socket = sock

    def cancel(self):
        try:
            try:
                self.data_socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            self.data_socket.close()
        except Exception:
            pass


def handle_stou(command, client_socket, client_session):
    """Maneja comando STOU (Store Unique) - Guarda un archivo con nombre único"""

    if not client_session.is_authenticated():
        client_session.send_response(client_socket, 530, "Not logged in")
        return

    data_socket, _ = client_session.get_pasv_info()
    if not data_socket:
        client_session.send_response(client_socket, 425, "Use PASV first")
        return

    original_filename = command.get_arg(0) if command.arg_count() > 0 else "file"
    user_root = client_session.root_directory

    try:
        unique_filename = fs_manager.generate_unique_filename(user_root, client_session.current_directory, original_filename)
    except Exception as e:
        client_session.send_response(client_socket, 450, str(e))
        return

    try:
        data_conn, _ = data_socket.accept()
    except socket.error:
        client_session.send_response(client_socket, 425, "Can't open data connection")
        client_session.cleanup_pasv()
        return

    # register transfer
    transfer = TransferObj(data_conn)
    tid = client_session.start_transfer(transfer)

    try:
        client_session.send_response(client_socket, 150, f'File: {unique_filename}')
        success, message = fs_manager.store_stream(user_root, client_session.current_directory, unique_filename, sock_reader(data_conn))
        try:
            data_conn.close()
        except Exception:
            pass

        if success:
            client_session.send_response(client_socket, 250, f'{unique_filename}')
        else:
            client_session.send_response(client_socket, 550, message)

    except SecurityError as e:
        client_session.send_response(client_socket, 550, str(e))
    except Exception:
        client_session.send_response(client_socket, 450, "Requested file action not taken")

    finally:
        client_session.finish_transfer(tid)
        client_session.cleanup_pasv()