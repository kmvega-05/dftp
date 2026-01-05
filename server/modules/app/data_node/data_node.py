import socket
import threading
import logging

from typing import Dict
from server.modules.discovery import LocationNode, NodeType
from server.modules.comm import Message, MessageType
from server.modules.app.data_node.file_system_manager import FileSystemManager, SecurityError
from server.modules.app.data_node.metadata import FileMetadata, MetadataTable

logger = logging.getLogger("dftp.app.data_node")

class DataNode(LocationNode):
    """
    DataNode:
    - Maneja operaciones de filesystem (lectura/escritura) para los clientes FTP.
    - Mantiene sockets PASV activos por session_id.
    - Garantiza seguridad de paths y bloqueo concurrente usando FileSystemManager.
    """
    def __init__(self, node_name: str, ip: str, port: int, fs_root : str, discovery_timeout : float = 0.8, heartbeat_interval: int = 2):

        super().__init__(node_name, ip, port, NodeType.DATA, discovery_timeout, heartbeat_interval)

        self.fs = FileSystemManager(fs_root)

        # session_id -> passive socket
        self._pasv_sockets: Dict[str, socket.socket] = {}
        self._lock = threading.Lock()

        self.metadata_table = MetadataTable(f"{fs_root}/metadata.json")

        self._register_handlers()

    # --------------------------------------------------
    # Registration
    # --------------------------------------------------

    def _register_handlers(self):
        self.register_handler(MessageType.DATA_CWD, self._handle_cwd)
        self.register_handler(MessageType.DATA_MKD, self._handle_mkd)
        self.register_handler(MessageType.DATA_REMOVE, self._handle_remove)
        self.register_handler(MessageType.DATA_RENAME, self._handle_rename)
        self.register_handler(MessageType.DATA_STAT, self._handle_stat)
        self.register_handler(MessageType.DATA_OPEN_PASV, self._handle_open_pasv)
        self.register_handler(MessageType.DATA_LIST, self._handle_list)
        self.register_handler(MessageType.DATA_RETR_FILE, self._handle_retr)
        self.register_handler(MessageType.DATA_STORE_FILE, self._handle_store)
        self.register_handler(MessageType.DATA_META_REQUEST, self._handle_data_meta_request)

    def _handle_cwd(self, message: Message):
        user = message.payload.get("user")
        current_path = message.payload.get("current_path")
        new_path = message.payload.get("new_path")

        if not user or current_path is None or new_path is None:
            return Message(MessageType.DATA_CWD_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Missing required arguments"})

        try:
            namespace = self.fs.get_namespace(user)
            virtual, _ = self.fs.validate_path(namespace, current_path, new_path, want="dir")
            return Message(MessageType.DATA_CWD_ACK, self.ip, message.header.get("src"), payload={"cwd": virtual}, metadata={"status": "OK"})

        except FileNotFoundError:
            return Message(MessageType.DATA_CWD_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Directory not found"})

        except NotADirectoryError:
            return Message(MessageType.DATA_CWD_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Not a directory"})

        except SecurityError:
            return Message(MessageType.DATA_CWD_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Invalid path"})

        except Exception as e:
            logger.exception("CWD failed: %s", e)
            return Message(MessageType.DATA_CWD_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": str(e)})


    def _handle_mkd(self, message: Message):
        user = message.payload.get("user")
        path = message.payload.get("path")
        cwd = message.payload.get("cwd", "/")

        if not user or not path:
            return Message(MessageType.DATA_MKD_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Missing required arguments"})

        try:
            namespace = self.fs.get_namespace(user)
            self.fs.make_dir(namespace, cwd, path)
            return Message(MessageType.DATA_MKD_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "OK"})

        except FileExistsError:
            return Message(MessageType.DATA_MKD_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Failed to create directory: Directory already exists"})

        except SecurityError:
            return Message(MessageType.DATA_MKD_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Failed to create directory: Invalid path"})

        except Exception as e:
            logger.exception("Error creating directory: %s", e)
            return Message(MessageType.DATA_MKD_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": str(e)})

    def _handle_remove(self, message: Message):
        user = message.payload.get("user")
        path = message.payload.get("path")
        cwd = message.payload.get("cwd", "/")
        target_type = message.payload.get("type", "file")

        if not user or not path:
            return Message(MessageType.DATA_REMOVE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Missing required arguments"})

        try:
            namespace = self.fs.get_namespace(user)
            if target_type == "file":
                self.fs.delete_file(namespace, cwd, path)
            else:
                self.fs.remove_dir(namespace, cwd, path)

            virtual_path = self.fs.normalize_virtual_path(cwd, path)
            return Message(MessageType.DATA_REMOVE_ACK, self.ip, message.header.get("src"), payload={"path": virtual_path}, metadata={"status": "OK"})

        except FileNotFoundError:
            return Message(MessageType.DATA_REMOVE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Path not found"})

        except SecurityError:
            return Message(MessageType.DATA_REMOVE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Invalid path"})

        except OSError as e:
            return Message(MessageType.DATA_REMOVE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": str(e)})

        except Exception as e:
            logger.exception("Error removing path: %s", e)
            return Message(MessageType.DATA_REMOVE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": str(e)})


    def _handle_rename(self, message: Message):
        user = message.payload.get("user")
        cwd = message.payload.get("cwd")
        old_path = message.payload.get("old_path")
        new_path = message.payload.get("new_path")

        if user is None or cwd is None or old_path is None or new_path is None:
            return Message(MessageType.DATA_RENAME_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Missing required arguments"})

        try:
            root_dir = self.fs.get_namespace(user)
            self.fs.rename_path(root_dir, cwd, old_path, new_path)
            return Message(MessageType.DATA_RENAME_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "OK"})

        except Exception as e:
            logger.exception(str(e))
            return Message(MessageType.DATA_RENAME_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": str(e)})

    def _handle_stat(self, message: Message) -> Message:
        user = message.payload.get("user")
        cwd = message.payload.get("cwd")
        path = message.payload.get("path")

        if user is None or cwd is None or path is None:
            return Message(MessageType.DATA_STAT_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Missing required arguments"})

        try:
            root = self.fs.get_namespace(user)
            stat = self.fs.stat(root, cwd, path)

            if stat is None:
                raise FileNotFoundError("Path not found")

            return Message(MessageType.DATA_STAT_ACK, self.ip, message.header.get("src"), payload={"stat": stat}, metadata={"status": "OK"})

        except Exception as e:
            logger.exception(str(e))
            return Message(MessageType.DATA_STAT_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": str(e)})


    def _handle_open_pasv(self, message: Message):
        session_id = message.payload.get("session_id")

        if session_id is None:
            return Message(MessageType.DATA_OPEN_PASV_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Missing required arguments"})

        sock = None
        try:
            sock, ip, port = self._open_pasv_socket()
        except Exception:
            logger.exception("Unable to open PASV socket")
            self._try_close_socket(sock)
            return Message(MessageType.DATA_OPEN_PASV_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Unable to open data socket"})

        with self._lock:
            old_sock = self._pasv_sockets.pop(session_id, None)
            if old_sock:
                self._try_close_socket(old_sock)
            self._pasv_sockets[session_id] = sock

        return Message(MessageType.DATA_OPEN_PASV_ACK, self.ip, message.header.get("src"), payload={"ip": ip, "port": port}, metadata={"status": "OK"})

    def _open_pasv_socket(self) -> tuple[socket.socket, str, int]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.ip, 0))
        sock.listen(1)
        sock.settimeout(300)
        return sock, sock.getsockname()[0], sock.getsockname()[1]


    def _consume_pasv_socket(self, session_id: str) -> socket.socket | None:
        with self._lock:
            return self._pasv_sockets.pop(session_id, None)


    def _try_close_socket(self, sock: socket.socket) -> None:
        if sock:
            sock.close()

    def _handle_list(self, message: Message) -> Message:
        payload = message.payload or {}
        session_id = payload.get("session_id")
        user = payload.get("user")
        cwd = payload.get("cwd", "/")
        path = payload.get("path", ".")
        detailed = payload.get("detailed", False)

        if not session_id or not user:
            return Message(MessageType.DATA_LIST_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Missing arguments"})

        # Obtener socket pasivo perteneciente a la sesion
        sock = self._consume_pasv_socket(session_id)
        if not sock:
            return Message(MessageType.DATA_LIST_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "No passive socket"})

        try:
            # Aceptar conexión de datos
            data_conn, data_addr = sock.accept()

            # Listar filesystem
            namespace = self.fs.get_namespace(user)
            if detailed:
                entries = self.fs.list_dir_with_stats(namespace, cwd, path)
                lines = [f'{e["permissions"]:o} 1 owner group {e["size"]:>8} {e["modified"]} {e["name"]}' for e in entries]
            else:
                entries = self.fs.list_dir(namespace, cwd, path)
                lines = entries

            # Hacer que se envie '150 Data Connection Ready' al cliente
            ready_msg = Message(MessageType.DATA_READY, self.ip, message.header.get("src"), payload={"session_id": session_id})
            
            logger.info("Sending DATA READY message to Processing Node")
            
            ack = self.send_message(message.header.get("src"), 9000, ready_msg, await_response=True, timeout=30)
            
            logger.info("RECEIVED : %s", ack)
            
            if not ack or not ack.payload.get("success"):
                logger.info("Sending : 'Unable to prepare data conection.'")
                return Message(MessageType.DATA_LIST_ACK, self.ip, message.header.get("src"), payload={}, metadata = {"status": "error", "message": "Unable to prepare data conection."})

            logger.info("Sending List DATA to %s", data_addr)
            # 4. Enviar datos
            for entry in lines:
                line = f"{entry}\r\n"
                data_conn.sendall(line.encode())

            logger.info("Data sent.")

            if data_conn:
                data_conn.close()
            
            logger.info("LIST Exitoso")
            return Message(MessageType.DATA_LIST_ACK, self.ip, message.header.get("src"), payload={}, metadata = {"status": "OK"})

        except Exception as e:
            logger.exception("LIST failed")
            return Message(MessageType.DATA_LIST_ACK, self.ip, message.header.get("src"), payload={}, metadata = {"status": "error", "message": str(e)})

        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _handle_retr(self, message: Message):
        session_id = message.payload.get("session_id")
        user = message.payload.get("user")
        cwd = message.payload.get("cwd")
        path = message.payload.get("path")
        chunk_size = message.payload.get("chunk_size", 65536)

        if not all([session_id, user, cwd, path]):
            return Message(MessageType.DATA_RETR_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Missing required arguments"})

        sock = self._consume_pasv_socket(session_id)
        if not sock:
            return Message(MessageType.DATA_RETR_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "No passive socket for session"})

        try:
            namespace = self.fs.get_namespace(user)
            generator = self.fs.read_stream(namespace, cwd, path, chunk_size=chunk_size)

            # Avisamos al routing node que ya puede enviar el 150 al cliente
            self.send_message(message.header.get("src"), 9000, Message(MessageType.DATA_READY, self.ip, message.header.get("src"), payload={"session_id": session_id}))

            conn, addr = sock.accept()
            logger.info("Sending file...")
            with conn:
                for chunk in generator:
                    conn.sendall(chunk)
            logger.info("File sent")

        except Exception as e:
            logger.exception(str(e))
            return Message(MessageType.DATA_RETR_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": str(e)})
        finally:
            try:
                sock.close()
            except:
                pass
        logger.info("RETR exitoso")
        return Message(MessageType.DATA_RETR_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "OK"})

    def _handle_store(self, message: Message):
        
        session_id = message.payload.get("session_id")
        user = message.payload.get("user")
        cwd = message.payload.get("cwd")
        path = message.payload.get("path")
        chunk_size = message.payload.get("chunk_size", 65536)

        if not all([session_id, user, cwd, path]):
            return Message(MessageType.DATA_STORE_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Missing required arguments"})

        sock = self._consume_pasv_socket(session_id)
        if not sock:
            return Message(MessageType.DATA_STORE_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "No passive socket for session"})

        try:
            namespace = self.fs.get_namespace(user)

            # Avisamos al routing node que ya puede enviar el 150 al cliente
            self.send_message(message.header.get("src"), 9000, Message(MessageType.DATA_READY, self.ip, message.header.get("src"), payload={"session_id": session_id}))

            conn, addr = sock.accept()
            with conn:
                def data_gen():
                    while True:
                        chunk = conn.recv(chunk_size)
                        if not chunk:
                            break
                        yield chunk

                self.fs.write_stream(namespace, cwd, path, data_gen(), chunk_size=chunk_size)

        except Exception as e:
            logger.exception(str(e))
            return Message(MessageType.DATA_STORE_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": str(e)})
        finally:
            sock.close()

        return Message(MessageType.DATA_STORE_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "OK"})

    def _handle_data_meta_request(self, message: Message) -> Message:
        """
        Maneja DATA_META_REQUEST.
        Devuelve metadatos de un archivo específico o de todos los archivos.
        """
        payload = message.payload or {}
        filename = payload.get("filename")

        try:
            if filename:
                meta = self.metadata_table.get(filename)
                metadata = [meta.to_dict()] if meta else []
            else:
                metadata = [m.to_dict() for m in self.metadata_table.all()]

            return Message(type=MessageType.DATA_META_REQUEST_ACK, src=self.ip, dst=message.header.get("src"), payload={"success": True, "metadata": metadata})

        except Exception:
            logger.exception("[%s] Error procesando DATA_META_REQUEST", self.node_name)
            return Message(type=MessageType.DATA_META_REQUEST_ACK, src=self.ip, dst=message.header.get("src"), payload={"success": False, "metadata": []})
