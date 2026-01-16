import posixpath
import socket
import threading
import logging
import os
import time
import uuid

from typing import Dict
from server.modules.consistency.gossip_node import GossipNode
from server.modules.discovery import LocationNode, NodeType
from server.modules.comm import Message, MessageType
from server.modules.app.data_node.file_system_manager import FileSystemManager, SecurityError
from server.modules.app.data_node.metadata import FileMetadata, MetadataTable

logger = logging.getLogger("dftp.app.data_node")

K_REPLICAS = int(os.environ.get("DATA_NODE_REPLICATION_K", 1))

class DataNode(GossipNode):
    """
    DataNode:
    - Maneja operaciones de filesystem (lectura/escritura) para los clientes FTP.
    - Mantiene sockets PASV activos por session_id.
    - Garantiza seguridad de paths y bloqueo concurrente usando FileSystemManager.
    """
    def __init__(self, node_name: str, ip: str, port: int, fs_root : str, discovery_timeout : float = 0.8, heartbeat_interval: int = 2):
        # Initialize ALL attributes BEFORE calling super().__init__() to avoid race conditions
        # when the gossip thread tries to use _merge_state() or other methods
        self.data_lock = threading.Lock()
        self._lock = threading.Lock()
        self.fs = FileSystemManager(fs_root)
        self._pasv_sockets: Dict[str, socket.socket] = {}
        self.metadata_table = MetadataTable(f"{fs_root}/metadata.json")
        
        # Flag to indicate when initialization is complete
        self.initialized = False

        super().__init__(node_name=node_name, ip=ip, port=port, node_role=NodeType.DATA, discovery_timeout=discovery_timeout, heartbeat_interval=heartbeat_interval)

        self._register_handlers()
        
        # Mark as initialized after all setup is complete
        self.initialized = True
        logger.info("[%s] DataNode completamente inicializado y listo para merge", self.node_name)

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
        # Replicación de directorios y eliminaciones
        self.register_handler(MessageType.DATA_REPLICATE_DIR_CREATE, self._handle_replicate_dir_create)
        self.register_handler(MessageType.DATA_REPLICATE_DIR_DELETE, self._handle_replicate_dir_delete)
        self.register_handler(MessageType.DATA_REPLICATE_FILE_DELETE, self._handle_replicate_file_delete)
        self.register_handler(MessageType.DATA_REPLICATE_RENAME, self._handle_replicate_rename)
        # File sync during merge (using PASV-like socket transfer)
        self.register_handler(MessageType.DATA_SYNC_FILE_REQUEST, self._handle_sync_file_request)
        self.register_handler(MessageType.DATA_SYNC_FILE_READY, self._handle_sync_file_ready)
        self.register_handler(MessageType.SEND_STATE, self._handle_send_state)

    def send_state(self, peer_ip):
        # Don't merge until initialization is complete
        logger.info("[DEBUG] Verificando si se paso el peer_ip correctamente desde %s", peer_ip)
        if not self.initialized:
            logger.warning("[%s] Merge solicitado pero nodo no inicializado aún, ignorando", self.node_name)
            return
        
        # Copiar metadatos y estructura de directorios dentro del lock, pero luego liberar ANTES de enviar mensaje
        with self.data_lock:
            metadata_table_dict = {"metadatas":[m.to_dict() for m in self.metadata_table.all()]}
            dir_structure = self._export_directory_structure()
        
        payload = {
            "metadatas": metadata_table_dict.get("metadatas", []),
            "directories": dir_structure
        }
        
        msg = Message(type=MessageType.SEND_STATE, src=self.ip, dst=peer_ip, payload=payload)
        try:
            logger.info("[%s] Enviando SEND_STATE a %s (con %d directorios)", self.node_name, peer_ip, len(dir_structure))
            # Esperar respuesta SIN sostener el lock para evitar deadlock
            self.send_message(peer_ip, 9000, msg, await_response=False, timeout=30)
            logger.info("[%s] Recibido SEND_STATE_ACK de %s", self.node_name, peer_ip)
        except Exception as e:
            logger.exception("[%s] Error durante SEND_STATE con %s: %s", self.node_name, peer_ip, e)

    def _merge_state(self, peer_ip):
        # Don't merge until initialization is complete
        logger.info("[DEBUG] Verificando si se paso el peer_ip correctamente desde %s", peer_ip)
        if not self.initialized:
            logger.warning("[%s] Merge solicitado pero nodo no inicializado aún, ignorando", self.node_name)
            return
        
        # Copiar metadatos y estructura de directorios dentro del lock, pero luego liberar ANTES de enviar mensaje
        with self.data_lock:
            metadata_table_dict = {"metadatas":[m.to_dict() for m in self.metadata_table.all()]}
            dir_structure = self._export_directory_structure()
        
        payload = {
            "metadatas": metadata_table_dict.get("metadatas", []),
            "directories": dir_structure
        }
        
        msg = Message(type=MessageType.MERGE_STATE, src=self.ip, dst=peer_ip, payload=payload)
        try:
            logger.info("[%s] Enviando MERGE_STATE a %s (con %d directorios)", self.node_name, peer_ip, len(dir_structure))
            # Esperar respuesta SIN sostener el lock para evitar deadlock
            response = self.send_message(peer_ip, 9000, msg, await_response=True, timeout=30)
            logger.info("[%s] Recibido MERGE_STATE_ACK de %s", self.node_name, peer_ip)
            
            # Procesar directorios del peer
            if response and response.payload.get("directories"):
                logger.info("[%s] Importando %d directorios del peer", self.node_name, len(response.payload.get("directories", [])))
                self._import_directory_structure(response.payload.get("directories", []))
            
            # Procesar archivos del peer
            if response and response.payload.get("metadatas"):
                for metadata in response.payload.get("metadatas", []):
                    self._on_gossip_update({"op":"add", "metadata": metadata}, peer_ip=peer_ip)
            logger.info("[%s] MERGE_STATE completado con %s", self.node_name, peer_ip)
        except Exception as e:
            logger.exception("[%s] Error durante MERGE_STATE con %s: %s", self.node_name, peer_ip, e)

    def _on_gossip_update(self, update: dict, peer_ip: str = None):
        """
        Aplica cambios recibidos via gossip (add/delete).
        
        Maneja conflictos de nombres:
        - Si dos archivos tienen el mismo nombre pero transfer_id diferente,
          el archivo con MENOR transfer_id se renombra a file_copy.txt
        - Se sincroniza el archivo del peer si no existe localmente
        """
        op = update.get("op")
        metadata_dict = update.get("metadata")
        if not op or not metadata_dict:
            return
        
        filename = metadata_dict["filename"]
        transfer_id_incoming = metadata_dict["transfer_id"]
        
        with self.data_lock:
            if op == "add":
                existing = self.metadata_table.get(filename)
                
                if existing:
                    existing_transfer_id = existing.to_dict()["transfer_id"]
                    
                    # Mismo transfer_id = mismo archivo, solo actualizar
                    if existing_transfer_id == transfer_id_incoming:
                        logger.info("[%s] Metadato ya existe con mismo transfer_id: %s", 
                                   self.node_name, filename)
                        return
                    
                    # Transfer_ids diferentes = conflicto de nombres, diferentes contenidos
                    logger.info("[%s] Conflicto detectado: archivo %s con transfer_ids diferentes. "
                               "Existente: %s, Incoming: %s", 
                               self.node_name, filename, existing_transfer_id, transfer_id_incoming)
                    
                    # Determinar cuál renombrar: el de MENOR transfer_id
                    if existing_transfer_id < transfer_id_incoming:
                        # El archivo LOCAL tiene menor transfer_id → renombrar LOCAL
                        logger.info("[%s] Local %s tiene transfer_id menor (%s < %s), renombrando local a copy",
                                   self.node_name, filename, existing_transfer_id, transfer_id_incoming)
                        
                        # Renombrar archivo local
                        name, ext = os.path.splitext(filename)
                        renamed_filename = f"{name}_copy{ext}"
                        
                        old_local_path = os.path.join(self.fs.root_dir, filename)
                        new_local_path = os.path.join(self.fs.root_dir, renamed_filename)
                        
                        if os.path.exists(old_local_path):
                            try:
                                os.rename(old_local_path, new_local_path)
                                logger.info("[%s] Renombrado: %s → %s", self.node_name, 
                                           filename, renamed_filename)
                            except Exception as e:
                                logger.error("[%s] Error renombrando archivo %s: %s", 
                                           self.node_name, filename, e)
                        
                        # Actualizar metadatos del archivo local renombrado
                        existing.filename = renamed_filename
                        self.metadata_table.upsert(existing)
                        
                        # Ahora agregar el nuevo metadato (incoming) con el nombre original
                        fm = FileMetadata.from_dict(metadata_dict)
                        self.metadata_table.upsert(fm)
                        logger.info("[%s] Metadato agregado para archivo incoming: %s", 
                                   self.node_name, filename)
                    else:
                        # El archivo INCOMING tiene menor o igual transfer_id → renombrar INCOMING
                        logger.info("[%s] Incoming %s tiene transfer_id menor o igual (%s <= %s), renombrando incoming a copy",
                                   self.node_name, filename, transfer_id_incoming, existing_transfer_id)
                        
                        # Renombrar el metadato incoming
                        name, ext = os.path.splitext(filename)
                        renamed_filename = f"{name}_copy{ext}"
                        metadata_dict["filename"] = renamed_filename
                        
                        fm = FileMetadata.from_dict(metadata_dict)
                        self.metadata_table.upsert(fm)
                        logger.info("[%s] Metadato agregado para archivo renombrado: %s", 
                                   self.node_name, renamed_filename)
                        
                        # Actualizar filename para la sincronización
                        filename = renamed_filename
                else:
                    # No existe conflicto, solo agregar
                    fm = FileMetadata.from_dict(metadata_dict)
                    self.metadata_table.upsert(fm)
                    logger.info("[%s] Metadato agregado via gossip: %s (transfer_id: %s)", 
                               self.node_name, filename, transfer_id_incoming)
                
                # Verificar si necesitamos sincronizar el archivo desde el peer
                if peer_ip:
                    local_path = os.path.join(self.fs.root_dir, filename)
                    if not os.path.exists(local_path):
                        logger.info("[%s] Archivo no existe localmente, solicitando a %s: %s", 
                                   self.node_name, peer_ip, filename)
                        # Iniciar sincronización async desde el peer
                        sync_thread = threading.Thread(
                            target=self._sync_file_from_peer,
                            args=(peer_ip, filename),
                            daemon=True
                        )
                        sync_thread.start()
                    else:
                        logger.info("[%s] Archivo ya existe localmente: %s", self.node_name, filename)

    def _handle_send_state(self, message):
        peer_ip = message.header.get("src")
        logger.info("[%s] Recibiendo SEND_STATE de %s (con %d directorios)", self.node_name, peer_ip, len(message.payload.get("directories", [])))
        
        # Importar estructura de directorios primero
        if message.payload.get("directories"):
            self._import_directory_structure(message.payload.get("directories", []))
        
        # Luego importar metadatos de archivos
        for metadata in message.payload.get("metadatas", []):
            self._on_gossip_update({"op":"add", "metadata": metadata}, peer_ip=peer_ip)
    
    def _handle_merge_state(self, message: Message) -> Message:
        """
        Recibe MERGE_STATE de otro nodo, aplica los metadatos y estructura de directorios,
        y retorna MERGE_STATE_ACK con el estado propio.
        """
        peer_ip = message.header.get("src")
        logger.info("[%s] Recibiendo MERGE_STATE de %s (con %d directorios)", self.node_name, peer_ip, len(message.payload.get("directories", [])))
        
        # Importar estructura de directorios primero
        if message.payload.get("directories"):
            self._import_directory_structure(message.payload.get("directories", []))
        
        # Luego importar metadatos de archivos
        for metadata in message.payload.get("metadatas", []):
            self._on_gossip_update({"op":"add", "metadata": metadata}, peer_ip=peer_ip)

        with self.data_lock:
            metadata_table_dict = {"metadatas":[m.to_dict() for m in self.metadata_table.all()]}
            dir_structure = self._export_directory_structure()
        
        payload = {
            "metadatas": metadata_table_dict.get("metadatas", []),
            "directories": dir_structure
        }
        
        logger.info("[%s] Enviando MERGE_STATE_ACK a %s (con %d directorios)", self.node_name, peer_ip, len(dir_structure))
        return Message(type=MessageType.MERGE_STATE_ACK, src=self.ip, dst=peer_ip, payload=payload)
    
    def _sync_file_from_peer(self, peer_ip: str, filename: str):
        """
        Solicita un archivo al peer usando un socket PASV dedicado.
        Se ejecuta en un hilo separado para no bloquear.
        """
        try:
            logger.info("[%s] Iniciando sincronización de archivo %s desde %s", self.node_name, filename, peer_ip)
            
            # Enviar solicitud de sync - el peer abrirá un socket PASV
            msg = Message(
                type=MessageType.DATA_SYNC_FILE_REQUEST,
                src=self.ip,
                dst=peer_ip,
                payload={"filename": filename}
            )
            
            response = self.send_message(peer_ip, 9000, msg, await_response=True, timeout=30)
            
            if response and response.header.get("type") == MessageType.DATA_SYNC_FILE_READY:
                # Recibimos el puerto PASV donde descargar el archivo
                pasv_port = response.payload.get("pasv_port")
                if pasv_port:
                    self._download_file_from_pasv(peer_ip, pasv_port, filename)
                else:
                    logger.error("[%s] No se recibió puerto PASV para %s", self.node_name, filename)
            else:
                logger.error("[%s] No se pudo obtener puerto PASV para %s de %s", self.node_name, filename, peer_ip)
                
        except Exception as e:
            logger.exception("[%s] Error durante sincronización de %s desde %s: %s", 
                           self.node_name, filename, peer_ip, e)
    
    def _download_file_from_pasv(self, peer_ip: str, pasv_port: int, filename: str):
        """
        Descarga archivo del socket PASV del peer.
        """
        sock = None
        try:
            logger.info("[%s] Conectando a PASV en %s:%d para descargar %s", 
                       self.node_name, peer_ip, pasv_port, filename)
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(300)  # 5 minutos de timeout
            sock.connect((peer_ip, pasv_port))
            
            # Guardar archivo - filename incluye el namespace (ej: "anonymous/beltran.txt")
            local_path = os.path.join(self.fs.root_dir, filename)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            file_size = 0
            with open(local_path, "wb") as f:
                while True:
                    data = sock.recv(65536)  # 64KB chunks
                    if not data:
                        break
                    f.write(data)
                    file_size += len(data)
            
            logger.info("[%s] Archivo %s descargado desde %s (%d bytes)", 
                       self.node_name, filename, peer_ip, file_size)
            
        except Exception as e:
            logger.exception("[%s] Error descargando archivo %s desde %s:%d: %s", 
                           self.node_name, filename, peer_ip, pasv_port, e)
        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass
    
    def _handle_sync_file_request(self, message: Message) -> Message:
        """
        Recibe solicitud de sincronización de archivo.
        Abre un socket PASV para que el peer descargue el archivo.
        """
        filename = message.payload.get("filename")
        peer_ip = message.header.get("src")
        
        logger.info("[%s] Recibida solicitud de sincronización para %s desde %s", 
                   self.node_name, filename, peer_ip)
        
        try:
            # filename ahora incluye el namespace (ej: "anonymous/beltran.txt")
            # Resolver a ruta real: /tmp/ftp_root/anonymous/beltran.txt
            local_path = os.path.join(self.fs.root_dir, filename)
            
            if not os.path.exists(local_path):
                logger.error("[%s] Archivo no existe: %s (ruta real: %s)", self.node_name, filename, local_path)
                return Message(
                    type=MessageType.DATA_SYNC_FILE_READY,
                    src=self.ip,
                    dst=peer_ip,
                    payload={"filename": filename, "status": "NOT_FOUND"}
                )
            
            # Abrir socket PASV en un puerto disponible
            pasv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            pasv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            pasv_sock.bind((self.ip, 0))  # Puerto automático
            pasv_sock.listen(1)
            pasv_port = pasv_sock.getsockname()[1]
            
            logger.info("[%s] Socket PASV abierto en puerto %d para archivo %s", 
                       self.node_name, pasv_port, filename)
            
            # Responder con el puerto PASV
            response = Message(
                type=MessageType.DATA_SYNC_FILE_READY,
                src=self.ip,
                dst=peer_ip,
                payload={"filename": filename, "pasv_port": pasv_port, "status": "READY"}
            )
            
            # Iniciar hilo para servir el archivo
            serve_thread = threading.Thread(
                target=self._serve_file_on_pasv,
                args=(pasv_sock, local_path),
                daemon=True
            )
            serve_thread.start()
            logger.info("[%s] Hilo iniciado enviando confirmacion", self.node_name)
            return response
            
        except Exception as e:
            logger.exception("[%s] Error preparando archivo %s para envío: %s", 
                           self.node_name, filename, e)
            return Message(
                type=MessageType.DATA_SYNC_FILE_READY,
                src=self.ip,
                dst=peer_ip,
                payload={"filename": filename, "status": "ERROR", "error": str(e)}
            )
    
    def _serve_file_on_pasv(self, pasv_sock: socket.socket, local_path: str):
        """
        Sirve un archivo a través del socket PASV.
        Se ejecuta en un hilo separado.
        """
        client_sock = None
        try:
            logger.debug("[%s] Esperando conexión PASV para archivo %s", self.node_name, local_path)
            client_sock, client_addr = pasv_sock.accept()
            logger.info("[%s] Cliente %s conectado a PASV para descargar %s", 
                       self.node_name, client_addr, local_path)
            
            file_size = os.path.getsize(local_path)
            
            with open(local_path, "rb") as f:
                bytes_sent = 0
                while True:
                    chunk = f.read(65536)  # 64KB chunks
                    if not chunk:
                        break
                    client_sock.sendall(chunk)
                    bytes_sent += len(chunk)
            
            logger.info("[%s] Archivo %s enviado via PASV (%d bytes)", 
                       self.node_name, local_path, bytes_sent)
            
        except Exception as e:
            logger.exception("[%s] Error sirviendo archivo %s por PASV: %s", 
                           self.node_name, local_path, e)
        finally:
            if client_sock:
                try:
                    client_sock.close()
                except:
                    pass
            if pasv_sock:
                try:
                    pasv_sock.close()
                except:
                    pass
    
    def _handle_sync_file_ready(self, message: Message) -> Message:
        """
        Manejador dummy para DATA_SYNC_FILE_READY.
        Este mensaje es respuesta, no se espera como solicitud.
        """
        logger.warning("[%s] Recibido DATA_SYNC_FILE_READY sin esperarlo", self.node_name)
        return None
    
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
            
            # Replicate directory creation to other DataNodes
            virtual_path = self.fs.normalize_virtual_path(cwd, path)
            self._replicate_dir_create(user, virtual_path)
            
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
            
            # Replicate removal to other DataNodes
            if target_type == "file":
                self._replicate_file_delete(user, virtual_path)
            else:
                self._replicate_dir_delete(user, virtual_path)
            
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
            
            # Replicate rename to other DataNodes
            old_virtual_path = self.fs.normalize_virtual_path(cwd, old_path)
            new_virtual_path = self.fs.normalize_virtual_path(cwd, new_path)
            self._replicate_rename(user, old_virtual_path, new_virtual_path)
            
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

        # *** VERIFICAR EXISTENCIA DEL ARCHIVO ANTES DE CONSUMIR EL SOCKET ***
        try:
            namespace = self.fs.get_namespace(user)
            
            # Normalizar path y verificar existencia
            virtual_path = self.fs.normalize_virtual_path(cwd, path)
            real_path = self.fs.virtual_to_real_path(namespace, virtual_path)
            
            logger.info("[%s] RETR: user=%s, cwd=%s, path=%s → virtual_path=%s, real_path=%s", 
                       self.node_name, user, cwd, path, virtual_path, real_path)
            
            if not os.path.exists(real_path) or not os.path.isfile(real_path):
                logger.error("[%s] RETR: Archivo no existe o no es archivo: %s", self.node_name, real_path)
                # Retornar error SIN consumir el socket PASV
                return Message(MessageType.DATA_RETR_FILE_ACK, self.ip, message.header.get("src"), 
                             payload={}, metadata={"status": "error", "message": f"File not found: {path}"})
        except Exception as e:
            logger.exception("[%s] RETR: Error validando archivo: %s", self.node_name, e)
            return Message(MessageType.DATA_RETR_FILE_ACK, self.ip, message.header.get("src"), 
                         payload={}, metadata={"status": "error", "message": str(e)})
        
        # *** AHORA SÍ CONSUMIR EL SOCKET PASV ***
        sock = self._consume_pasv_socket(session_id)
        if not sock:
            return Message(MessageType.DATA_RETR_FILE_ACK, self.ip, message.header.get("src"), 
                         payload={}, metadata={"status": "error", "message": "No passive socket for session"})

        try:
            # Crear generator DESPUÉS de verificar que el archivo existe
            generator = self.fs.read_stream(namespace, cwd, path, chunk_size=chunk_size)

            # Avisamos al routing node que ya puede enviar el 150 al cliente
            logger.info("[%s] Notifying processing node %s DATA_READY for session %s", self.node_name, message.header.get("src"), session_id)
            self.send_message(message.header.get("src"), 9000, Message(MessageType.DATA_READY, self.ip, message.header.get("src"), payload={"session_id": session_id}), await_response=False)

            conn, addr = sock.accept()
            logger.info("[%s] Sending file for session %s...", self.node_name, session_id)
            with conn:
                for chunk in generator:
                    conn.sendall(chunk)
            logger.info("[%s] File sent for session %s", self.node_name, session_id)

        except Exception as e:
            logger.exception("[%s] RETR transfer error: %s", self.node_name, str(e))
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
            self.send_message(message.header.get("src"), 9000, Message(MessageType.DATA_READY, self.ip, message.header.get("src"), payload={"session_id": session_id}), await_response=False)

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
            
            # Guardar ruta completa incluyendo namespace en metadata
            # Formato: namespace/virtual_path (ej: "anonymous/beltran.txt")
            # IMPORTANTE: usar posixpath para consistencia multiplataforma
            full_metadata_path = posixpath.join(user, virtual_path.lstrip("/"))

            # Crear y guardar metadata local
            file_metadata = FileMetadata(filename=full_metadata_path, version=version, transfer_id=transfer_id, timestamp=time.time())
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

            # Esperamos hasta recibir K acks con timeout de 5 minutos
            if not replicate_to:
                ack_event.set()
            else:
                # Timeout: 5 minutos para replicación completa
                max_wait = 300  # 5 minutos
                ack_received = ack_event.wait(timeout=max_wait)
                if not ack_received:
                    logger.warning("[%s] Replication timeout after %d seconds, received %d acks out of %d", self.node_name, max_wait, ack_counter[0], len(replicate_to))

            # 5️⃣ Retornamos respuesta al cliente
            status = "OK" if ack_counter[0] >= min(K_REPLICAS, len(replicate_to)) else "partial"
            logger.info("[%s] Replication finished for %s, acks_received=%s, required=%s, status=%s", self.node_name, virtual_path, ack_counter[0], min(K_REPLICAS, len(replicate_to)), status)

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
        
        Payload esperado:
            - filename: str (nombre del archivo a buscar)
            - cwd: str (directorio actual del cliente)
            - user: str (usuario/namespace - REQUERIDO para buscar correctamente)
        """
        payload = message.payload or {}
        filename = payload.get("filename")
        cwd = payload.get("cwd", "/")
        user = payload.get("user")  # NUEVO: obtener el usuario

        logger.info("[%s] Received DATA_META_REQUEST from %s payload=%s", self.node_name, message.header.get("src"), message.payload)
        logger.info("[%s] Buscando archivo: filename=%s, cwd=%s, user=%s", self.node_name, filename, cwd, user)
        try:
            if filename:
                # Normalizar path virtual
                virtual_path = self.fs.normalize_virtual_path(cwd, filename)
                
                # Construir la ruta completa con namespace (igual que en STOR)
                # Si user no viene, buscar en metadata table directamente
                if user:
                    full_metadata_path = posixpath.join(user, virtual_path.lstrip("/"))
                    logger.info("[%s] Buscando con ruta completa: %s", self.node_name, full_metadata_path)
                    meta = self.metadata_table.get(full_metadata_path)
                else:
                    logger.info("[%s] Sin user, buscando solo por virtual_path: %s", self.node_name, virtual_path)
                    meta = self.metadata_table.get(virtual_path)
                
                logger.info("[%s] Found: %s", self.node_name, meta)
                metadata = [meta.to_dict()] if meta else []
            
            else:
                logger.info("[%s] Retrieving all metadata")
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

            # Esperar conexión del nodo que enviará el archivo - timeout de 5 minutos
            sock.settimeout(300)
            logger.debug("[%s] Waiting for connection on %s:%s with timeout 300s", self.node_name, listen_ip, listen_port)
            conn, addr = sock.accept()
            logger.debug("[%s] Connection accepted from %s", self.node_name, addr)
            
            with conn:
                # Timeout en lectura: 60 segundos de inactividad
                conn.settimeout(60)
                bytes_received = 0
                
                def chunk_gen():
                    nonlocal bytes_received
                    while True:
                        try:
                            chunk = conn.recv(chunk_size)
                            if not chunk:
                                logger.debug("[%s] No more data, received %d bytes total", self.node_name, bytes_received)
                                break
                            bytes_received += len(chunk)
                            logger.debug("[%s] Received chunk: %d bytes (total: %d bytes)", self.node_name, len(chunk), bytes_received)
                            yield chunk
                        except socket.timeout:
                            logger.error("[%s] Socket timeout while receiving file data (received %d bytes so far)", self.node_name, bytes_received)
                            raise TimeoutError(f"Socket timeout after receiving {bytes_received} bytes")

                # Guardar archivo en filesystem
                namespace = self.fs.get_namespace(user)
                logger.info("[%s] Writing file %s for user %s", self.node_name, filename, user)
                self.fs.write_stream(namespace, cwd, filename, chunk_gen(), chunk_size=chunk_size)
                logger.info("[%s] File received and written: %d bytes", self.node_name, bytes_received)

            # Actualizar metadata
            self.metadata_table.upsert(file_metadata)
            logger.info("[%s] Replicated file stored: %s for user %s", self.node_name, filename, user)
            return Message(MessageType.DATA_REPLICATE_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "OK"})

        except socket.timeout as e:
            logger.error("[%s] DATA_REPLICATE_FILE timeout: %s", self.node_name, e)
            return Message(MessageType.DATA_REPLICATE_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": f"Timeout: {e}"})
        
        except Exception as e:
            logger.exception("[%s] DATA_REPLICATE_FILE failed: %s", self.node_name, e)
            return Message(MessageType.DATA_REPLICATE_FILE_ACK, self.ip, message.header.get("src"), payload={}, metadata={"status": "error", "message": str(e)})

        finally:
            try:
                if sock:
                    sock.close()
            except:
                pass

    def _handle_replicate_ready(self, message: Message):
        """
        Maneja DATA_REPLICATE_READY:
        - Se conecta al nodo destino usando IP/puerto indicados.
        - Envía el archivo en stream con timeouts adecuados.
        """
        payload = message.payload or {}
        ip = payload.get("ip")
        port = payload.get("port")
        filename = payload.get("filename")
        user = payload.get("user")
        cwd = payload.get("cwd")

        logger.info("[%s] Received DATA_REPLICATE_READY from %s payload=%s", self.node_name, message.header.get("src"), message.payload)
        
        if not all([ip, port, filename, user, cwd]):
            logger.error("[%s] Missing required fields in DATA_REPLICATE_READY", self.node_name)
            return  # Mensaje de control, no return de respuesta

        try:
            # Determinar la ruta real y generar stream del archivo
            namespace = self.fs.get_namespace(user)

            logger.info("[%s] Connecting to %s:%s to send file %s (user=%s, cwd=%s)", self.node_name, ip, port, filename, user, cwd)
            
            # Generador de chunks
            chunk_gen = self.fs.read_stream(namespace, cwd, filename)

            # Conectar al nodo destino con timeout
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(30)  # timeout de conexión: 30 segundos
                logger.debug("[%s] Connecting with 30s timeout", self.node_name)
                sock.connect((ip, port))
                logger.debug("[%s] Connected successfully", self.node_name)
                
                # Timeout en envío: 60 segundos de inactividad
                sock.settimeout(60)
                bytes_sent = 0
                chunk_count = 0
                
                logger.info("[%s] Sending file '%s' to %s:%s", self.node_name, filename, ip, port)
                for chunk in chunk_gen:
                    try:
                        sock.sendall(chunk)
                        bytes_sent += len(chunk)
                        chunk_count += 1
                        logger.debug("[%s] Sent chunk %d: %d bytes (total: %d bytes)", self.node_name, chunk_count, len(chunk), bytes_sent)
                    except socket.timeout:
                        logger.error("[%s] Socket timeout while sending to %s:%s (sent %d bytes in %d chunks)", self.node_name, ip, port, bytes_sent, chunk_count)
                        raise TimeoutError(f"Socket timeout after sending {bytes_sent} bytes")

            logger.info("[%s] File '%s' sent successfully to %s:%s (%d bytes in %d chunks)", self.node_name, filename, ip, port, bytes_sent, chunk_count)

        except socket.timeout as e:
            logger.error("[%s] Connection timeout while replicating file '%s' to %s:%s: %s", self.node_name, filename, ip, port, e)
        
        except Exception as e:
            logger.exception("[%s] Error replicating file '%s' to %s:%s: %s", self.node_name, filename, ip, port, e)

    def _replicate_to_node(self, target_ip: str, file_metadata: FileMetadata, path: str, user: str, cwd: str, ack_counter: list, ack_lock: threading.Lock, ack_event: threading.Event, total_peers : int):
        """
        Envía DATA_REPLICATE_FILE a un nodo objetivo y actualiza contador de acks.
        Incluye reintentos para archivos grandes.
        """
        max_retries = 3
        retry_delay = 2  # segundos
        
        for attempt in range(max_retries):
            try:
                logger.info("[%s] Sending DATA_REPLICATE_FILE to %s for %s (attempt %d/%d)", self.node_name, target_ip, path, attempt + 1, max_retries)
                
                # Aumentar timeout para archivos grandes: 30 segundos + tiempo variable
                timeout = 30.0 + (attempt * 5)  # aumenta con cada reintento
                
                replicate_msg = Message(type=MessageType.DATA_REPLICATE_FILE, src=self.ip, dst=target_ip, payload={"filename": path, "metadata": file_metadata.to_dict(), "user": user, "cwd": cwd})
                ack = self.send_message(target_ip, 9000, replicate_msg, await_response=True, timeout=timeout)
                
                logger.info("[%s] Received replicate ack from %s: %s", self.node_name, target_ip, ack)
                
                if ack and ack.metadata.get("status") == "OK":
                    with ack_lock:
                        ack_counter[0] += 1
                        logger.info("[%s] Ack counter incremented: %s", self.node_name, ack_counter[0])
                        if ack_counter[0] >= min(K_REPLICAS, total_peers):
                            ack_event.set()
                    return  # éxito, salir
                else:
                    logger.warning("[%s] Replication to %s returned status: %s", self.node_name, target_ip, ack.metadata.get("status") if ack else "None")
            
            except Exception as e:
                logger.warning("[%s] Error sending replicate to %s (attempt %d/%d): %s", self.node_name, target_ip, attempt + 1, max_retries, e)
                
                if attempt < max_retries - 1:
                    logger.info("[%s] Retrying in %d seconds...", self.node_name, retry_delay)
                    time.sleep(retry_delay)
                else:
                    logger.error("[%s] Replication failed to %s after %d attempts", self.node_name, target_ip, max_retries)

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

    # --------------------------------------------------
    # Directory and File Replication (MKD, RMD, DELE)
    # --------------------------------------------------

    def _replicate_dir_create(self, user: str, virtual_path: str):
        """
        Replica la creación de un directorio a todos los otros DataNodes.
        Se ejecuta en un hilo separado para no bloquear la operación original.
        """
        def broadcast():
            try:
                peer_nodes = self.query_by_role(NodeType.DATA)
                for peer in peer_nodes:
                    if peer["ip"] == self.ip:
                        continue  # No enviar a uno mismo
                    
                    logger.info("[%s] Replicating dir create to %s: %s", self.node_name, peer["ip"], virtual_path)
                    try:
                        self.send_message(
                            peer["ip"], 9000,
                            Message(
                                type=MessageType.DATA_REPLICATE_DIR_CREATE,
                                src=self.ip,
                                dst=peer["ip"],
                                payload={"user": user, "virtual_path": virtual_path}
                            ),
                            await_response=False
                        )
                    except Exception as e:
                        logger.warning("[%s] Failed to replicate dir create to %s: %s", self.node_name, peer["ip"], e)
            except Exception as e:
                logger.warning("[%s] Error broadcasting dir create: %s", self.node_name, e)
        
        t = threading.Thread(target=broadcast, daemon=True)
        t.start()

    def _replicate_dir_delete(self, user: str, virtual_path: str):
        """
        Replica la eliminación de un directorio a todos los otros DataNodes.
        Se ejecuta en un hilo separado para no bloquear la operación original.
        """
        def broadcast():
            try:
                peer_nodes = self.query_by_role(NodeType.DATA)
                for peer in peer_nodes:
                    if peer["ip"] == self.ip:
                        continue
                    
                    logger.info("[%s] Replicating dir delete to %s: %s", self.node_name, peer["ip"], virtual_path)
                    try:
                        self.send_message(
                            peer["ip"], 9000,
                            Message(
                                type=MessageType.DATA_REPLICATE_DIR_DELETE,
                                src=self.ip,
                                dst=peer["ip"],
                                payload={"user": user, "virtual_path": virtual_path}
                            ),
                            await_response=False
                        )
                    except Exception as e:
                        logger.warning("[%s] Failed to replicate dir delete to %s: %s", self.node_name, peer["ip"], e)
            except Exception as e:
                logger.warning("[%s] Error broadcasting dir delete: %s", self.node_name, e)
        
        t = threading.Thread(target=broadcast, daemon=True)
        t.start()

    def _replicate_file_delete(self, user: str, virtual_path: str):
        """
        Replica la eliminación de un archivo a todos los otros DataNodes.
        Se ejecuta en un hilo separado para no bloquear la operación original.
        """
        def broadcast():
            try:
                peer_nodes = self.query_by_role(NodeType.DATA)
                for peer in peer_nodes:
                    if peer["ip"] == self.ip:
                        continue
                    
                    logger.info("[%s] Replicating file delete to %s: %s", self.node_name, peer["ip"], virtual_path)
                    try:
                        self.send_message(
                            peer["ip"], 9000,
                            Message(
                                type=MessageType.DATA_REPLICATE_FILE_DELETE,
                                src=self.ip,
                                dst=peer["ip"],
                                payload={"user": user, "virtual_path": virtual_path}
                            ),
                            await_response=False
                        )
                    except Exception as e:
                        logger.warning("[%s] Failed to replicate file delete to %s: %s", self.node_name, peer["ip"], e)
            except Exception as e:
                logger.warning("[%s] Error broadcasting file delete: %s", self.node_name, e)
        
        t = threading.Thread(target=broadcast, daemon=True)
        t.start()

    def _replicate_rename(self, user: str, old_virtual_path: str, new_virtual_path: str):
        """
        Replica el renombrado de archivo/directorio a todos los otros DataNodes.
        Se ejecuta en un hilo separado para no bloquear la operación original.
        """
        def broadcast():
            try:
                peer_nodes = self.query_by_role(NodeType.DATA)
                for peer in peer_nodes:
                    if peer["ip"] == self.ip:
                        continue
                    
                    logger.info("[%s] Replicating rename to %s: %s -> %s", self.node_name, peer["ip"], old_virtual_path, new_virtual_path)
                    try:
                        self.send_message(
                            peer["ip"], 9000,
                            Message(
                                type=MessageType.DATA_REPLICATE_RENAME,
                                src=self.ip,
                                dst=peer["ip"],
                                payload={"user": user, "old_virtual_path": old_virtual_path, "new_virtual_path": new_virtual_path}
                            ),
                            await_response=False
                        )
                    except Exception as e:
                        logger.warning("[%s] Failed to replicate rename to %s: %s", self.node_name, peer["ip"], e)
            except Exception as e:
                logger.warning("[%s] Error broadcasting rename: %s", self.node_name, e)
        
        t = threading.Thread(target=broadcast, daemon=True)
        t.start()

    # --------------------------------------------------
    # Handlers for Directory and File Replication
    # --------------------------------------------------

    def _handle_replicate_dir_create(self, message: Message) -> Message:
        """
        Recibe replica de creación de directorio desde otro nodo.
        """
        user = message.payload.get("user")
        virtual_path = message.payload.get("virtual_path")
        
        logger.info("[%s] Received replicate dir create: user=%s path=%s", self.node_name, user, virtual_path)
        
        if not user or not virtual_path:
            return Message(MessageType.DATA_REPLICATE_DIR_CREATE, self.ip, message.header.get("src"), 
                         payload={}, metadata={"status": "error", "message": "Missing required fields"})
        
        try:
            namespace = self.fs.get_namespace(user)
            # Extract directory name and parent path from virtual_path
            parts = virtual_path.rstrip("/").rsplit("/", 1)
            if len(parts) == 2:
                cwd, dirname = parts
                cwd = "/" + cwd if not cwd.startswith("/") else cwd
            else:
                cwd = "/"
                dirname = virtual_path.lstrip("/")
            
            # Create directory if it doesn't exist
            try:
                self.fs.make_dir(namespace, cwd, dirname)
                logger.info("[%s] Replicated dir created: %s/%s", self.node_name, user, virtual_path)
            except FileExistsError:
                logger.info("[%s] Dir already exists locally: %s/%s", self.node_name, user, virtual_path)
            
            return Message(MessageType.DATA_REPLICATE_DIR_CREATE, self.ip, message.header.get("src"),
                         payload={}, metadata={"status": "OK"})
        
        except Exception as e:
            logger.exception("[%s] Error replicating dir create: %s", self.node_name, e)
            return Message(MessageType.DATA_REPLICATE_DIR_CREATE, self.ip, message.header.get("src"),
                         payload={}, metadata={"status": "error", "message": str(e)})

    def _handle_replicate_dir_delete(self, message: Message) -> Message:
        """
        Recibe replica de eliminación de directorio desde otro nodo.
        """
        user = message.payload.get("user")
        virtual_path = message.payload.get("virtual_path")
        
        logger.info("[%s] Received replicate dir delete: user=%s path=%s", self.node_name, user, virtual_path)
        
        if not user or not virtual_path:
            return Message(MessageType.DATA_REPLICATE_DIR_DELETE, self.ip, message.header.get("src"),
                         payload={}, metadata={"status": "error", "message": "Missing required fields"})
        
        try:
            namespace = self.fs.get_namespace(user)
            # Extract directory name and parent path from virtual_path
            parts = virtual_path.rstrip("/").rsplit("/", 1)
            if len(parts) == 2:
                cwd, dirname = parts
                cwd = "/" + cwd if not cwd.startswith("/") else cwd
            else:
                cwd = "/"
                dirname = virtual_path.lstrip("/")
            
            # Remove directory if it exists
            try:
                self.fs.remove_dir(namespace, cwd, dirname)
                logger.info("[%s] Replicated dir deleted: %s/%s", self.node_name, user, virtual_path)
            except FileNotFoundError:
                logger.info("[%s] Dir does not exist locally: %s/%s", self.node_name, user, virtual_path)
            
            return Message(MessageType.DATA_REPLICATE_DIR_DELETE, self.ip, message.header.get("src"),
                         payload={}, metadata={"status": "OK"})
        
        except Exception as e:
            logger.exception("[%s] Error replicating dir delete: %s", self.node_name, e)
            return Message(MessageType.DATA_REPLICATE_DIR_DELETE, self.ip, message.header.get("src"),
                         payload={}, metadata={"status": "error", "message": str(e)})

    def _handle_replicate_file_delete(self, message: Message) -> Message:
        """
        Recibe replica de eliminación de archivo desde otro nodo.
        """
        user = message.payload.get("user")
        virtual_path = message.payload.get("virtual_path")
        
        logger.info("[%s] Received replicate file delete: user=%s path=%s", self.node_name, user, virtual_path)
        
        if not user or not virtual_path:
            return Message(MessageType.DATA_REPLICATE_FILE_DELETE, self.ip, message.header.get("src"),
                         payload={}, metadata={"status": "error", "message": "Missing required fields"})
        
        try:
            namespace = self.fs.get_namespace(user)
            # Extract filename and parent path from virtual_path
            parts = virtual_path.rstrip("/").rsplit("/", 1)
            if len(parts) == 2:
                cwd, filename = parts
                cwd = "/" + cwd if not cwd.startswith("/") else cwd
            else:
                cwd = "/"
                filename = virtual_path.lstrip("/")
            
            # Delete file if it exists
            try:
                self.fs.delete_file(namespace, cwd, filename)
                logger.info("[%s] Replicated file deleted: %s/%s", self.node_name, user, virtual_path)
            except FileNotFoundError:
                logger.info("[%s] File does not exist locally: %s/%s", self.node_name, user, virtual_path)
            
            return Message(MessageType.DATA_REPLICATE_FILE_DELETE, self.ip, message.header.get("src"),
                         payload={}, metadata={"status": "OK"})
        
        except Exception as e:
            logger.exception("[%s] Error replicating file delete: %s", self.node_name, e)
            return Message(MessageType.DATA_REPLICATE_FILE_DELETE, self.ip, message.header.get("src"),
                         payload={}, metadata={"status": "error", "message": str(e)})

    def _handle_replicate_rename(self, message: Message) -> Message:
        """
        Recibe replica de renombrado desde otro nodo.
        """
        user = message.payload.get("user")
        old_virtual_path = message.payload.get("old_virtual_path")
        new_virtual_path = message.payload.get("new_virtual_path")
        
        logger.info("[%s] Received replicate rename: user=%s %s -> %s", self.node_name, user, old_virtual_path, new_virtual_path)
        
        if not user or not old_virtual_path or not new_virtual_path:
            return Message(MessageType.DATA_REPLICATE_RENAME, self.ip, message.header.get("src"),
                         payload={}, metadata={"status": "error", "message": "Missing required fields"})
        
        try:
            namespace = self.fs.get_namespace(user)
            # Extract old name and parent path
            old_parts = old_virtual_path.rstrip("/").rsplit("/", 1)
            if len(old_parts) == 2:
                cwd, old_name = old_parts
                cwd = "/" + cwd if not cwd.startswith("/") else cwd
            else:
                cwd = "/"
                old_name = old_virtual_path.lstrip("/")
            
            # Extract new name
            new_parts = new_virtual_path.rstrip("/").rsplit("/", 1)
            new_name = new_parts[-1]
            
            # Rename if old path exists
            try:
                self.fs.rename_path(namespace, cwd, old_name, new_name)
                logger.info("[%s] Replicated rename completed: %s -> %s", self.node_name, old_virtual_path, new_virtual_path)
            except FileNotFoundError:
                logger.info("[%s] Source path does not exist locally: %s", self.node_name, old_virtual_path)
            
            return Message(MessageType.DATA_REPLICATE_RENAME, self.ip, message.header.get("src"),
                         payload={}, metadata={"status": "OK"})
        
        except Exception as e:
            logger.exception("[%s] Error replicating rename: %s", self.node_name, e)
            return Message(MessageType.DATA_REPLICATE_RENAME, self.ip, message.header.get("src"),
                         payload={}, metadata={"status": "error", "message": str(e)})

    # --------------------------------------------------
    # Directory Structure Export/Import (MERGE_STATE)
    # --------------------------------------------------

    def _export_directory_structure(self) -> list:
        """
        Exporta la estructura completa de directorios para todos los usuarios/namespaces.
        Retorna una lista de paths virtuales de directorios que existen en este nodo.
        
        Ejemplo:
        [
            {"user": "anonymous", "virtual_path": "/"},
            {"user": "anonymous", "virtual_path": "/docs"},
            {"user": "anonymous", "virtual_path": "/docs/subfolder"},
            {"user": "beltran", "virtual_path": "/"},
            {"user": "beltran", "virtual_path": "/uploads"},
        ]
        """
        directories = []
        
        try:
            # Iterar por cada namespace (usuario)
            root_path = self.fs.root_dir
            if not os.path.exists(root_path):
                return directories
            
            for namespace in os.listdir(root_path):
                namespace_full_path = os.path.join(root_path, namespace)
                
                if not os.path.isdir(namespace_full_path):
                    continue
                
                # Recolectar todos los directorios en este namespace
                for dirpath, dirnames, filenames in os.walk(namespace_full_path):
                    # Convertir a path virtual relativo al namespace
                    rel_path = os.path.relpath(dirpath, namespace_full_path)
                    
                    if rel_path == ".":
                        virtual_path = "/"
                    else:
                        # Convertir a posix path y agregar /
                        virtual_path = "/" + rel_path.replace(os.sep, "/")
                    
                    directories.append({
                        "user": namespace,
                        "virtual_path": virtual_path
                    })
                    
                    logger.debug("[%s] Exported dir: user=%s, path=%s", self.node_name, namespace, virtual_path)
            
            logger.info("[%s] Exported %d directories", self.node_name, len(directories))
            return directories
        
        except Exception as e:
            logger.exception("[%s] Error exporting directory structure: %s", self.node_name, e)
            return directories

    def _import_directory_structure(self, directories: list) -> None:
        """
        Importa una estructura de directorios desde otro nodo durante merge.
        Crea todos los directorios que no existan localmente.
        
        Args:
            directories: Lista de dicts con {"user": namespace, "virtual_path": path}
        """
        created_count = 0
        skipped_count = 0
        
        try:
            for dir_info in directories:
                user = dir_info.get("user")
                virtual_path = dir_info.get("virtual_path")
                
                if not user or not virtual_path:
                    logger.warning("[%s] Invalid directory info: %s", self.node_name, dir_info)
                    continue
                
                try:
                    namespace = self.fs.get_namespace(user)
                    
                    # Convertir path virtual a path real
                    real_path = self.fs.virtual_to_real_path(namespace, virtual_path)
                    
                    # Crear directorio si no existe
                    if not os.path.exists(real_path):
                        os.makedirs(real_path, exist_ok=True)
                        logger.info("[%s] Created directory: user=%s, path=%s", self.node_name, user, virtual_path)
                        created_count += 1
                    else:
                        logger.debug("[%s] Directory already exists: user=%s, path=%s", self.node_name, user, virtual_path)
                        skipped_count += 1
                
                except Exception as e:
                    logger.warning("[%s] Error creating directory %s/%s: %s", self.node_name, user, virtual_path, e)
            
            logger.info("[%s] Imported directory structure: created=%d, skipped=%d", self.node_name, created_count, skipped_count)
        
        except Exception as e:
            logger.exception("[%s] Error importing directory structure: %s", self.node_name, e)
                         payload={}, metadata={"status": "error", "message": str(e)})
