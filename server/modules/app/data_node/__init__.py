__all__ = ["FileSystemManager", "SecurityError","DataNode"]

def __getattr__(name: str):
	if name in ("FileSystemManager", "SecurityError"):
		from .file_system_manager.file_system_manager import FileSystemManager, SecurityError
		return FileSystemManager if name == "FileSystemManager" else SecurityError
	if name == "DataNode":
		from .data_node import DataNode
		return DataNode
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
	return __all__