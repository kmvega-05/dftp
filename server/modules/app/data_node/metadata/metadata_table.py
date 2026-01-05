import json
import os
import threading

from typing import Dict, Optional, List
from server.modules.app.data_node.metadata.file_metadata import FileMetadata

class MetadataTable:
    """
    Tabla de metadatos de archivos para un DataNode.
    """

    def __init__(self, storage_path: str):
        self._storage_path = storage_path
        self._lock = threading.Lock()
        self._table: Dict[str, FileMetadata] = {}

        self._load()

    # =========================
    # Operaciones básicas
    # =========================

    def get(self, filename: str) -> Optional[FileMetadata]:
        with self._lock:
            return self._table.get(filename)

    def upsert(self, metadata: FileMetadata) -> None:
        """
        Inserta o actualiza los metadatos de un archivo.
        """
        with self._lock:
            self._table[metadata.filename] = metadata
            self._persist()

    def remove(self, filename: str) -> None:
        with self._lock:
            if filename in self._table:
                del self._table[filename]
                self._persist()

    def all(self) -> List[FileMetadata]:
        with self._lock:
            return list(self._table.values())

    # =========================
    # Persistencia
    # =========================

    def _persist(self) -> None:
        data = {filename: meta.to_dict() for filename, meta in self._table.items()}

        tmp_path = self._storage_path + ".tmp"

        with open(tmp_path, "w") as f:
            json.dump(data, f)

        os.replace(tmp_path, self._storage_path)

    def _load(self) -> None:
        if not os.path.exists(self._storage_path):
            return

        try:
            with open(self._storage_path, "r") as f:
                raw = json.load(f)

            for filename, meta_dict in raw.items():
                self._table[filename] = FileMetadata.from_dict(meta_dict)

        except Exception:
            # Si hay corrupción, arrancamos vacío
            self._table = {}
