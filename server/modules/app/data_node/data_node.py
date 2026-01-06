import socket
import threading
import logging
import os
import time
import uuid

from typing import Dict
from server.modules.discovery import LocationNode, NodeType
from server.modules.comm import Message, MessageType
from server.modules.app.data_node.file_system_manager import FileSystemManager, SecurityError
from server.modules.app.data_node.metadata import FileMetadata, MetadataTable

logger = logging.getLogger("dftp.app.data_node")

K_REPLICAS = int(os.environ.get("DATA_NODE_REPLICATION_K", 3))

class DataNode(LocationNode):
    """
    DataNode:
    - Maneja operaciones de filesystem (lectura/escritura) para los clientes FTP.
    - Mantiene sockets PASV activos por session_id.
    - Garantiza seguridad de paths y bloqueo concurrente usando FileSystemManager.
    """
    def __init__(self, node_name: str, ip: str, port: int, fs_root : str, discovery_timeout : float = 0.8, heartbeat_interval: int = 2):

        super().__init__(node_name=node_name, ip=ip, port=port, node_role=NodeType.DATA, discovery_timeout=discovery_timeout, heartbeat_interval=heartbeat_interval)

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
        self.register_handler(MessageType.DATA_REPLICATE_FILE, self._handle_replicate_file)
        self.register_handler(MessageType.DATA_REPLICATE_READY, self._handle_replicate_ready)

    def _handle_cwd(self, message: Message):
        logger.info("[%s] Received DATA_CWD from %s payload=%s", self.node_name, message.header.get("src"), message.payload)
        user = message.payload.get("user")
        current_path = message.payload.get("current_path")
        new_path = message.payload.get("new_path")

        if not user or current_path is None or new_path is None:
            return Message(MessageType.DATA_CWD_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Missing required arguments"})

        try:
            namespace = self.fs.get_namespace(user)
            virtual, _ = self.fs.validate_path(namespace, current_path, new_path, want="dir")
            logger.info("[%s] DATA_CWD success for %s -> %s", self.node_name, user, virtual)
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
        logger.info("[%s] Received DATA_MKD from %s payload=%s", self.node_name, message.header.get("src"), message.payload)
        user = message.payload.get("user")
        path = message.payload.get("path")
        cwd = message.payload.get("cwd", "/")

        if not user or not path:
            return Message(MessageType.DATA_MKD_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Missing required arguments"})

        try:
            namespace = self.fs.get_namespace(user)
            logger.info("[%s] Creating directory for %s: %s/%s", self.node_name, user, cwd, path)
            self.fs.make_dir(namespace, cwd, path)
            logger.info("[%s] DATA_MKD success for %s: %s/%s", self.node_name, user, cwd, path)
            return Message(MessageType.DATA_MKD_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "OK"})

        except FileExistsError:
            return Message(MessageType.DATA_MKD_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Failed to create directory: Directory already exists"})

        except SecurityError:
            return Message(MessageType.DATA_MKD_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Failed to create directory: Invalid path"})

        except Exception as e:
            logger.exception("Error creating directory: %s", e)
            return Message(MessageType.DATA_MKD_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": str(e)})

    def _handle_remove(self, message: Message):
        logger.info("[%s] Received DATA_REMOVE from %s payload=%s", self.node_name, message.header.get("src"), message.payload)
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
            logger.info("[%s] DATA_REMOVE success for %s: %s", self.node_name, user, virtual_path)
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
        logger.info("[%s] Received DATA_RENAME from %s payload=%s", self.node_name, message.header.get("src"), message.payload)
        user = message.payload.get("user")
        cwd = message.payload.get("cwd")
        old_path = message.payload.get("old_path")
        new_path = message.payload.get("new_path")

        if user is None or cwd is None or old_path is None or new_path is None:
            return Message(MessageType.DATA_RENAME_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Missing required arguments"})

        try:
            root_dir = self.fs.get_namespace(user)
            logger.info("[%s] Renaming %s:%s -> %s", self.node_name, user, old_path, new_path)
            self.fs.rename_path(root_dir, cwd, old_path, new_path)
            logger.info("[%s] DATA_RENAME success for %s: %s -> %s", self.node_name, user, old_path, new_path)
            return Message(MessageType.DATA_RENAME_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "OK"})

        except Exception as e:
            logger.exception(str(e))
            return Message(MessageType.DATA_RENAME_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": str(e)})

    def _handle_stat(self, message: Message) -> Message:
        logger.info("[%s] Received DATA_STAT from %s payload=%s", self.node_name, message.header.get("src"), message.payload)
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

            logger.info("[%s] DATA_STAT found for %s: %s -> %s", self.node_name, user, path, stat)
            return Message(MessageType.DATA_STAT_ACK, self.ip, message.header.get("src"), payload={"stat": stat}, metadata={"status": "OK"})

        except Exception as e:
            logger.exception(str(e))
            return Message(MessageType.DATA_STAT_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": str(e)})


    def _handle_open_pasv(self, message: Message):
        logger.info("[%s] Received DATA_OPEN_PASV from %s payload=%s", self.node_name, message.header.get("src"), message.payload)
        session_id = message.payload.get("session_id")

        if session_id is None:
            return Message(MessageType.DATA_OPEN_PASV_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Missing required arguments"})

        sock = None
        try:
            sock, ip, port = self._open_pasv_socket()
            logger.info("[%s] Opened PASV socket for session %s on %s:%s", self.node_name, session_id, ip, port)
        except Exception:
            logger.exception("Unable to open PASV socket")
            self._try_close_socket(sock)
            return Message(MessageType.DATA_OPEN_PASV_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Unable to open data socket"})

        with self._lock:
            old_sock = self._pasv_sockets.pop(session_id, None)
            if old_sock:
                self._try_close_socket(old_sock)
            self._pasv_sockets[session_id] = sock

        logger.info("[%s] DATA_OPEN_PASV_ACK sent for session %s -> %s:%s", self.node_name, session_id, ip, port)
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

        logger.info("[%s] Received DATA_LIST from %s payload=%s", self.node_name, message.header.get("src"), message.payload)
        
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
            logger.info("[%s] Sending DATA_READY to %s for session %s", self.node_name, message.header.get("src"), session_id)
            ack = self.send_message(message.header.get("src"), 9000, ready_msg, await_response=True, timeout=30)
            logger.info("[%s] Received ack for DATA_READY: %s", self.node_name, ack)
            if not ack or not ack.payload.get("success"):
                logger.info("[%s] Unable to prepare data connection on processing node %s", self.node_name, message.header.get("src"))
                return Message(MessageType.DATA_LIST_ACK, self.ip, message.header.get("src"), payload={}, metadata = {"status": "error", "message": "Unable to prepare data conection."})

            logger.info("Sending List DATA to %s", data_addr)
            # 4. Enviar datos
            for entry in lines:
                line = f"{entry}\r\n"
                data_conn.sendall(line.encode())

            logger.info("[%s] Data sent for LIST session %s", self.node_name, session_id)

            if data_conn:
                data_conn.close()
            
            logger.info("[%s] LIST successful for session %s", self.node_name, session_id)
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
        logger.info("[%s] Received DATA_RETR_FILE from %s payload=%s", self.node_name, message.header.get("src"), message.payload)
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
            logger.info("[%s] Notifying processing node %s DATA_READY for session %s", self.node_name, message.header.get("src"), session_id)
            self.send_message(message.header.get("src"), 9000, Message(MessageType.DATA_READY, self.ip, message.header.get("src"), payload={"session_id": session_id}))

            conn, addr = sock.accept()
            logger.info("[%s] Sending file for session %s...", self.node_name, session_id)
            with conn:
                for chunk in generator:
                    conn.sendall(chunk)
            logger.info("[%s] File sent for session %s", self.node_name, session_id)

        except Exception as e:
            logger.exception(str(e))
            return Message(MessageType.DATA_RETR_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": str(e)})
        
        finally:
            try:
                sock.close()
            except:
                pass
            
        logger.info("[%s] RETR successful for session %s", self.node_name, session_id)
        return Message(MessageType.DATA_RETR_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "OK"})

    
    def _handle_store(self, message: Message):
        logger.info("[%s] Received DATA_STORE_FILE from %s payload=%s", self.node_name, message.header.get("src"), message.payload)
        session_id = message.payload.get("session_id")
        user = message.payload.get("user")
        cwd = message.payload.get("cwd")
        path = message.payload.get("path")
        chunk_size = message.payload.get("chunk_size", 65536)
        replicate_to = message.payload.get("replicate_to", [])
        version = message.payload.get("version")
        transfer_id = message.payload.get("transfer_id")

        if not all([session_id, user, cwd, path, version, transfer_id]):
            return Message(MessageType.DATA_STORE_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Missing required arguments"})

        sock = self._consume_pasv_socket(session_id)
        if not sock:
            return Message(
                MessageType.DATA_STORE_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "No passive socket for session"})

        try:
            namespace = self.fs.get_namespace(user)

            # Avisamos al routing node que puede enviar el 150
            logger.info("[%s] Notifying processing node %s DATA_READY for session %s", self.node_name, message.header.get("src"), session_id)
            self.send_message(message.header.get("src"), 9000,Message(MessageType.DATA_READY, self.ip, message.header.get("src"), payload={"session_id": session_id}))

            # Guardar archivo localmente
            conn, addr = sock.accept()
            with conn:
                def data_gen():
                    while True:
                        chunk = conn.recv(chunk_size)
                        if not chunk:
                            break
                        yield chunk

                logger.info("[%s] Receiving and writing file %s for user %s", self.node_name, path, user)
                self.fs.write_stream(namespace, cwd, path, data_gen(), chunk_size=chunk_size)

            virtual_path = self.fs.normalize_virtual_path(cwd, path)

            # Crear y guardar metadata local
            file_metadata = FileMetadata(filename=virtual_path, version=version, transfer_id=transfer_id, timestamp=time.time())
            self.metadata_table.upsert(file_metadata)
            logger.info("[%s] Stored file %s and updated metadata", self.node_name, virtual_path)

            # Replicar en paralelo
            ack_counter = [0]  # lista para mutabilidad en threads
            ack_lock = threading.Lock()
            ack_event = threading.Event()

            logger.info("[%s] Starting replication to %s peers for %s", self.node_name, len(replicate_to), virtual_path)
            threads = [
                threading.Thread(target=self._replicate_to_node,
                    args=(ip, file_metadata, path, user, cwd, ack_counter, ack_lock, ack_event, len(replicate_to)))
                for ip in replicate_to]

            for t in threads:
                t.start()

            # Esperamos hasta recibir K acks
            if not replicate_to:
                ack_event.set()
            else:
                ack_event.wait()

            # 5️⃣ Retornamos respuesta al cliente
            status = "OK" if ack_counter[0] >= min(K_REPLICAS, len(replicate_to)) else "partial"
            logger.info("[%s] Replication finished for %s, acks_received=%s", self.node_name, virtual_path, ack_counter[0])

            return Message(MessageType.DATA_STORE_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": status, "acks_received": ack_counter[0]})

        except Exception as e:
            logger.exception(str(e))
            return Message(MessageType.DATA_STORE_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": str(e)})
        
        finally:
            sock.close()

    def _handle_data_meta_request(self, message: Message) -> Message:
        """
        Maneja DATA_META_REQUEST.
        Devuelve metadatos de un archivo específico o de todos los archivos.
        """
        payload = message.payload or {}
        filename = payload.get("filename")

        logger.info("[%s] Received DATA_META_REQUEST from %s payload=%s", self.node_name, message.header.get("src"), message.payload)
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

    def _handle_replicate_file(self, message: Message):
        payload = message.payload or {}
        filename = payload.get("filename")
        metadata_dict = payload.get("metadata")
        user = payload.get("user")
        cwd = payload.get("cwd")
        chunk_size = payload.get("chunk_size", 65536)

        logger.info("[%s] Received DATA_REPLICATE_FILE from %s payload=%s", self.node_name, message.header.get("src"), message.payload)
        
        if not filename or not metadata_dict or not user or cwd is None:
            return Message(MessageType.DATA_REPLICATE_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Missing required fields (filename, metadata, user, cwd)"})

        file_metadata = FileMetadata.from_dict(metadata_dict)

        sock = None
        try:
            # Preparar socket temporal para recibir el archivo
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.ip, 0))  # puerto aleatorio disponible
            sock.listen(1)
            listen_ip, listen_port = sock.getsockname()

            # Responder inmediatamente con IP/puerto y info del archivo
            ready_msg = Message(type=MessageType.DATA_REPLICATE_READY, src=self.ip, dst=message.header.get("src"), payload={"ip": listen_ip, "port": listen_port, "filename": filename, "user": user, "cwd": cwd})
            logger.info("[%s] Sending DATA_REPLICATE_READY to %s -> %s:%s", self.node_name, message.header.get("src"), listen_ip, listen_port)
            self.send_message(message.header.get("src"), 9000, ready_msg, await_response=False)

            # Esperar conexión del nodo que enviará el archivo
            conn, _ = sock.accept()
            with conn:
                def chunk_gen():
                    while True:
                        chunk = conn.recv(chunk_size)
                        if not chunk:
                            break
                        yield chunk

                # Guardar archivo en filesystem
                namespace = self.fs.get_namespace(user)
                self.fs.write_stream(namespace, cwd, filename, chunk_gen(), chunk_size=chunk_size)

            # Actualizar metadata
            self.metadata_table.upsert(file_metadata)
            logger.info("[%s] Replicated file stored: %s for user %s", self.node_name, filename, user)
            return Message(MessageType.DATA_REPLICATE_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "OK"})

        except Exception as e:
            logger.exception("DATA_REPLICATE_FILE failed: %s", e)
            return Message(MessageType.DATA_REPLICATE_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": str(e)})

        finally:
                try:
                    sock.close()
                except:
                    pass

    def _handle_replicate_ready(self, message: Message):
        """
        Maneja DATA_REPLICATE_READY:
        - Se conecta al nodo destino usando IP/puerto indicados.
        - Envía el archivo en stream.
        """
        payload = message.payload or {}
        ip = payload.get("ip")
        port = payload.get("port")
        filename = payload.get("filename")
        user = payload.get("user")
        cwd = payload.get("cwd")

        logger.info("[%s] Received DATA_REPLICATE_READY from %s payload=%s", self.node_name, message.header.get("src"), message.payload)
        
        if not all([ip, port, filename, user, cwd]):
            logger.error("Missing required fields in DATA_REPLICATE_READY")
            return  # Mensaje de control, no return de respuesta

        try:
            # Determinar la ruta real y generar stream del archivo
            namespace = self.fs.get_namespace(user)

            logger.info("[%s] Connecting to %s:%s to send file %s", self.node_name, ip, port, filename)
            
            # Generador de chunks
            chunk_gen = self.fs.read_stream(namespace, cwd, filename)

            # Conectar al nodo destino
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((ip, port))
                logger.info("Sending file '%s' to %s:%s", filename, ip, port)
                for chunk in chunk_gen:
                    sock.sendall(chunk)

            logger.info("[%s] File '%s' sent successfully to %s:%s", self.node_name, filename, ip, port)

        except Exception as e:
            logger.exception("[%s] Error replicating file '%s' to %s:%s: %s", self.node_name, filename, ip, port, e)

    def _replicate_to_node(self, target_ip: str, file_metadata: FileMetadata, path: str, user: str, cwd: str, ack_counter: list, ack_lock: threading.Lock, ack_event: threading.Event, total_peers : int):
        """
        Envía DATA_REPLICATE_FILE a un nodo objetivo y actualiza contador de acks.
        """
        try:
            logger.info("[%s] Sending DATA_REPLICATE_FILE to %s for %s", self.node_name, target_ip, path)
            replicate_msg = Message(type=MessageType.DATA_REPLICATE_FILE, src=self.ip, dst=target_ip, payload={"filename": path, "metadata": file_metadata.to_dict(), "user": user, "cwd": cwd})
            ack = self.send_message(target_ip, 9000, replicate_msg, await_response=True)  # sin timeout global
            logger.info("[%s] Received replicate ack from %s: %s", self.node_name, target_ip, ack)
            if ack and ack.metadata.get("status") == "OK":
                with ack_lock:
                    ack_counter[0] += 1
                    logger.info("[%s] Ack counter incremented: %s", self.node_name, ack_counter[0])
                    if ack_counter[0] >= min(K_REPLICAS, total_peers):
                        ack_event.set()
        
        except Exception as e:
            logger.exception("[%s] Error sending replicate to %s: %s", self.node_name, target_ip, e)
            # ignoramos errores de nodos individuales
            pass

    def _handle_rename_file(self, message: Message):
        logger.info("[%s] Received RENAME_FILE from %s payload=%s", self.node_name, message.header.get("src"), message.payload)
        payload = message.payload or {}
        filename = payload.get("filename")
        user = payload.get("user")
        cwd = payload.get("cwd")

        if not all([filename, user, cwd is not None]):
            return Message(MessageType.RENAME_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": "Missing required fields (filename, user, cwd)"})

        try:
            namespace = self.fs.get_namespace(user)

            # Generar un nombre único
            new_filename = self._generate_unique_filename(namespace, cwd, filename)

            # Renombrar archivo en filesystem
            self.fs.rename_path(namespace, cwd, filename, new_filename)

            # Actualizar metadata: eliminamos la antigua y creamos una nueva
            old_meta = self.metadata_table.get(filename)
            if old_meta:
                self.metadata_table.remove(filename)
            
            new_meta = FileMetadata(new_filename, 1, uuid.uuid4(), timestamp=time.time())
            self.metadata_table.upsert(new_meta)

            return Message(MessageType.RENAME_FILE_ACK, self.ip, message.header.get("src"), payload={"new_filename": new_filename}, metadata={"status": "OK"})

        except Exception as e:
            logger.exception("RENAME_FILE failed: %s", e)
            return Message(MessageType.RENAME_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": str(e)})


    def _generate_unique_filename(self, namespace: str, cwd: str, filename: str) -> str:
        """
        Genera un nombre único basado en `filename` dentro del cwd del namespace.
        Si `filename` ya existe, agrega un sufijo (1), (2), ... hasta encontrar uno disponible.
        """
        name, ext = os.path.splitext(filename)
        counter = 1
        new_filename = filename

        while True:
            try:
                # Intentamos validar; si existe, seguimos iterando
                self.fs.validate_path(namespace, cwd, new_filename, want="any")
                new_filename = f"{name}({counter}){ext}"
                counter += 1
            except FileNotFoundError:
                break  # nombre disponible

        return new_filename

