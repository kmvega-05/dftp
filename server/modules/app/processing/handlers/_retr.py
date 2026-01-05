import threading
import logging
from server.modules.app.processing import Command
from server.modules.discovery import NodeType
from server.modules.app.routing import ClientSession
from server.modules.comm import Message, MessageType

logger = logging.getLogger("dftp.processing.handlers.retr")

def handle_retr(cmd: Command, data: dict = None, processing_node=None) -> tuple[int, str, dict]:
    if not cmd.require_args(1):
        return 501, "Syntax error in parameters. Usage: RETR <filename>", None
    if not data or not processing_node:
        return 500, "Internal server error.", None

    session = ClientSession.from_json(data)
    filename = cmd.get_arg(0)
    if not session.is_authenticated():
        return 530, "Not logged in.", None

    data_nodes = processing_node.query_by_role(NodeType.DATA)
    if not data_nodes:
        return 451, "Requested action aborted. File system unavailable.", None

    file_candidates = []
    for node in data_nodes:
        try:
            meta_resp = processing_node.send_message(node["ip"], 9000, Message(type=MessageType.DATA_META_REQUEST, src=processing_node.ip, dst=node["ip"], payload={"filename": filename}), await_response=True, timeout=30)
            
            if meta_resp and meta_resp.payload.get("success"):
                for meta in meta_resp.payload.get("metadata", []):
                    if meta.get("filename") == filename:
                        file_candidates.append({"node": node, "version": meta.get("version", 1), "transfer_id": meta.get("transfer_id", "0")})
        
        except Exception as e:
            logger.warning("Failed to query metadata from DataNode (%s): %s", node["ip"], e)
            continue

    if not file_candidates:
        return 550, f"File '{filename}' not found.", None

    # Elegimos el nodo con mayor version y transfer_id
    file_candidates.sort(key=lambda x: (x["version"], x["transfer_id"]), reverse=True)
    max_version = file_candidates[0]["version"]
    max_transfer_id = file_candidates[0]["transfer_id"]

    # Actualizar nodos que tienen versión anterior
    threads = []
    for fc in file_candidates[1:]:
        node = fc["node"]
        version = fc["version"]
        transfer_id = fc["transfer_id"]
        
        if version < max_version or (version == max_version and transfer_id < max_transfer_id):
            t = threading.Thread(target=_update_node_from_peer, args=(processing_node, node["ip"], filename, file_candidates[0]["node"]["ip"]))
            t.start()
            threads.append(t)
            
    for t in threads:
        t.join()

    # Usar la IP de la sesión PASV como nodo que se comunica con el cliente
    pasv_info = session.get_pasv_mode_info()

    if not pasv_info:
        return 425, "Use PASV first.", None
    
    primary_ip, _ = pasv_info

    try:
        response = processing_node.send_message(primary_ip, 9000, Message(type=MessageType.DATA_RETR_FILE, src=processing_node.ip, dst=primary_ip, payload={"user": session.get_username(), "cwd": session.get_cwd(), "path": filename, "session_id": session.get_session_id(), "chunk_size": 65536}), await_response=True, timeout=300)

        if not response:
            return 451, "Requested action aborted. File transfer failed.", None
        if response.metadata.get("status") != "OK":
            return 550, response.metadata.get("message", "Failed to retrieve file."), None
        return 212, f"File '{filename}' retrieved successfully.", None

    except Exception as e:
        logger.exception("Failed to RETR file: %s", e)
        return 550, "Failed to retrieve file.", None


def _update_node_from_peer(processing_node, target_ip, filename, src_ip):
    try:
        processing_node.send_message(target_ip, 9000,
            Message(type=MessageType.DATA_REPLICATE_FILE, src=processing_node.ip, dst=target_ip, payload={"filename": filename, "update_from": src_ip}),
            await_response=True)
    except Exception as e:
        logger.warning("Failed to update node %s from %s: %s", target_ip, src_ip, e)
