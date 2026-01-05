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
    
    