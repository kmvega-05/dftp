__all__ = ["FileMetadata", "MetadataTable"]

def __getattr__(name: str):
	if name == "FileMetadata":
		from .file_metadata import FileMetadata
		return FileMetadata
	if name == "MetadataTable":
		from .metadata_table import MetadataTable
		return MetadataTable
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
	return __all__