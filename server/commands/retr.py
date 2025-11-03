import socket
from entities.file_system_manager import _GLOBAL_FSM as fs_manager, SecurityError

class TransferObj:
    def __init__(self, sock):
        self.data_socket = sock

    def cancel(self):
        try:
            # attempt an orderly shutdown before close
            try:
                self.data_socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            self.data_socket.close()
        except Exception:
            pass


def handle_retr(command, client_socket, client_session):
    """Maneja comando RETR - descarga de archivo mediante data connection (streaming)."""

    if not client_session.is_authenticated():
        client_session.send_response(client_socket, 530, "Not logged in")
        return

    if not command.require_args(1):
        client_session.send_response(client_socket, 501, "Syntax error in parameters")
        return

    data_socket, _ = client_session.get_pasv_info()
    if not data_socket:
        client_session.send_response(client_socket, 425, "Use PASV first")
        return

    filename = command.get_arg(0)
    user_root = client_session.root_directory

    try:
        # ensure resource exists and is a file
        fs_manager.exists(user_root, client_session.current_directory, filename, want='file')
    except Exception as e:
        client_session.send_response(client_socket, 550, str(e))
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
        client_session.send_response(client_socket, 150, f"Opening data connection for {filename}")

        gen = fs_manager.retrieve_stream(user_root, client_session.current_directory, filename)
        for chunk in gen:
            try:
                data_conn.sendall(chunk)
            except Exception:
                raise

        try:
            data_conn.close()
        except Exception:
            pass

        client_session.send_response(client_socket, 226, f"Transfer complete")

    except FileNotFoundError:
        client_session.send_response(client_socket, 550, "File not found")
    except SecurityError as e:
        client_session.send_response(client_socket, 550, str(e))
    except Exception:
        client_session.send_response(client_socket, 450, "Requested file action not taken")

    finally:
        client_session.finish_transfer(tid)
        client_session.cleanup_pasv()
