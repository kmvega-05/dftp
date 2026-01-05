from dataclasses import dataclass, asdict

@dataclass
class FileMetadata:
    filename: str
    version: int
    transfer_id: str
    timestamp: float

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "FileMetadata":
        return FileMetadata(
            filename=data["filename"],
            version=data["version"],
            transfer_id=data["transfer_id"],
            timestamp=data["timestamp"]
        )
    def __str__(self) -> str:
        return (f"FileMetadata(filename={self.filename}, "
                f"version={self.version}, "
                f"transfer_id={self.transfer_id}, "
                f"timestamp={self.timestamp})")
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def is_newer_than(self, other: "FileMetadata") -> bool:
        """
        Devuelve True si self es más reciente que other.
        Regla:
        - Mayor version → más reciente
        - Si versión igual → mayor transfer_id lexicográficamente → más reciente
        """
        if self.filename != other.filename:
            raise ValueError("No se pueden comparar metadatos de archivos diferentes.")
        
        if self.version > other.version:
            return True
        if self.version < other.version:
            return False
        # version igual → comparar transfer_id
        return self.transfer_id > other.transfer_id

    # Opcional: implementar comparaciones mágicas
    def __lt__(self, other: "FileMetadata") -> bool:
        return not self.is_newer_than(other) and self != other

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FileMetadata):
            return NotImplemented
        return (self.filename == other.filename and
                self.version == other.version and
                self.transfer_id == other.transfer_id)
    