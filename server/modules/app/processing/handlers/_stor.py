import logging
import uuid

from server.modules.app.processing import Command
from server.modules.discovery import NodeType
from server.modules.app.routing import ClientSession
from server.modules.comm import Message, MessageType

logger = logging.getLogger("dftp.processing.handlers.stor")

def handle_stor(cmd: Command, data: dict = None, processing_node=None) -> tuple[int, str, dict]:
    """Maneja el comando STOR <filename>"""

    if not cmd.require_args(1):
        return 501, "Syntax error in parameters. Usage: STOR <filename>", None
    if not data or not processing_node:
        return 500, "Internal server error.", None

    session = ClientSession.from_json(data)
    filename = cmd.get_arg(0)
    if not session.is_authenticated():
        return 530, "Not logged in.", None

    data_nodes = processing_node.query_by_role(NodeType.DATA)
    if not data_nodes:
        logger.warning("No DataNodes available for STOR")
        return 451, "Requested action aborted. File system unavailable.", None

    # Determinar versión consultando todos los metadatos
    max_version = 0
    for node in data_nodes:
        try:
            meta_req = Message(type=MessageType.DATA_META_REQUEST, src=processing_node.ip, dst=node["ip"], payload={"filename": filename})
            resp = processing_node.send_message(node["ip"], 9000, meta_req, await_response=True)
            
            if resp and resp.payload.get("metadata"):
                
                for meta in resp.payload["metadata"]:
                    
                    ver = meta.get("version", 0)
                    
                    if ver > max_version:
                        max_version = ver
        except Exception:
            pass

    version = max_version + 1
    transfer_id = str(uuid.uuid4())

    # Usamos la IP de la sesión PASV como primary
    pasv_info = session.get_pasv_mode_info()

    if not pasv_info:
        return 425, "Use PASV first.", None
    
    primary_ip, _ = pasv_info

    # Los demás nodos para replicar
    replicas = [n["ip"] for n in data_nodes if n["ip"] != primary_ip]

    msg = Message(type=MessageType.DATA_STORE_FILE, src=processing_node.ip, dst=primary_ip, payload={"session_id": session.get_session_id(), "user": session.get_username(), "cwd": session.get_cwd(), "path": filename, "version": version, "transfer_id": transfer_id, "replicate_to": replicas, "chunk_size": 65536})

    try:
        response = processing_node.send_message(primary_ip, 9000, msg, await_response=True)
        
    except Exception:
        logger.exception("STOR failed contacting DataNode %s", primary_ip)
        return 451, "Requested action aborted. File system unavailable.", None

    if not response:
        return 451, "Requested action aborted. File system unavailable.", None

    status = response.metadata.get("status")
    if status in ["OK", "partial"]:
        return 226, f"File '{filename}' stored successfully.", None

    return 550, response.metadata.get("message", "Failed to store file."), None
