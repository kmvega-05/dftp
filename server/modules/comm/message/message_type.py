class MessageType:
    """Clase estática que contiene constantes para los diferentes tipos de mensajes"""

    # =========================
    # Discovery messages
    # =========================
    DISCOVERY_HEARTBEAT = "DISCOVERY_HEARTBEAT"
    DISCOVERY_QUERY_BY_NAME = "DISCOVERY_QUERY_BY_NAME"
    DISCOVERY_QUERY_BY_ROLE = "DISCOVERY_QUERY_BY_ROLE"
    DISCOVERY_QUERY_ALL = "DISCOVERY_QUERY_ALL"

    DISCOVERY_HEARTBEAT_ACK = "DISCOVERY_HEARTBEAT_ACK"
    DISCOVERY_QUERY_BY_NAME_ACK = "DISCOVERY_QUERY_BY_NAME_ACK"
    DISCOVERY_QUERY_BY_ROLE_ACK = "DISCOVERY_QUERY_BY_ROLE_ACK"
    DISCOVERY_QUERY_ALL_ACK = "DISCOVERY_QUERY_ALL_ACK"

    # =========================
    # FTP processing
    # =========================
    PROCESS_FTP_COMMAND = "PROCESS_FTP_COMMAND"
    PROCESS_FTP_COMMAND_ACK = "PROCESS_FTP_COMMAND_ACK"

    # =========================
    # Auth
    # =========================
    AUTH_VALIDATE_USER = "AUTH_VALIDATE_USER"
    AUTH_VALIDATE_PASSWORD = "AUTH_VALIDATE_PASSWORD"

    AUTH_VALIDATE_USER_ACK = "AUTH_VALIDATE_USER_ACK"
    AUTH_VALIDATE_PASSWORD_ACK = "AUTH_VALIDATE_PASSWORD_ACK"

    # =========================
    # Data Node – FTP operations
    # =========================
    DATA_LIST = "DATA_LIST"
    DATA_STAT = "DATA_STAT"
    DATA_MKD = "DATA_MKD"
    DATA_REMOVE = "DATA_REMOVE"
    DATA_RENAME = "DATA_RENAME"
    DATA_CWD = "DATA_CWD"
    DATA_OPEN_PASV = "DATA_OPEN_PASV"
    DATA_RETR_FILE = "DATA_RETR_FILE"
    DATA_STORE_FILE = "DATA_STORE_FILE"
    DATA_READY = "DATA_READY"

    DATA_LIST_ACK = "DATA_LIST_ACK"
    DATA_STAT_ACK = "DATA_STAT_ACK"
    DATA_MKD_ACK = "DATA_MKD_ACK"
    DATA_REMOVE_ACK = "DATA_REMOVE_ACK"
    DATA_RENAME_ACK = "DATA_RENAME_ACK"
    DATA_CWD_ACK = "DATA_CWD_ACK"
    DATA_OPEN_PASV_ACK = "DATA_OPEN_PASV_ACK"
    DATA_RETR_FILE_ACK = "DATA_RETR_FILE_ACK"
    DATA_STORE_FILE_ACK = "DATA_STORE_FILE_ACK"
    DATA_READY_ACK = "DATA_READY_ACK"

    # =========================
    # Data Node – Replication (RRR)
    # =========================

    # Escrituras replicadas (STOR)
    DATA_REPLICATE_FILE = "DATA_REPLICATE_FILE"
    DATA_REPLICATE_FILE_ACK = "DATA_REPLICATE_FILE_ACK"

    DATA_REPLICATE_READY = "DATA_REPLICATE_READY"

    # Lectura de metadatos (RETR)
    DATA_META_REQUEST = "DATA_META_REQUEST"
    DATA_META_REQUEST_ACK = "DATA_META_ACK"

    # Read repair / sincronización
    UPDATE_FROM_NODE = "UPDATE_FROM_NODE"
    UPDATE_FROM_NODE_ACK = "UPDATE_ACK"

    # Resolución de conflictos
    RENAME_FILE = "RENAME_FILE"
    RENAME_FILE_ACK = "RENAME_FILE_ACK"

    # Bootstrap / join de nuevos DataNodes
    CLUSTER_STATE_REQUEST = "CLUSTER_STATE_REQUEST"
    CLUSTER_STATE_ACK = "CLUSTER_STATE_ACK"

    # Transferencia interna entre DataNodes
    DATA_PUSH = "DATA_PUSH"
    DATA_PUSH_ACK = "DATA_PUSH_ACK"
