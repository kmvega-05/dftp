__all__ = ["FileSystemManager", "SecurityError" ]

def __getattr__(name: str):
	if name == "FileSystemManager":
		from .file_system_manager import FileSystemManager
		return FileSystemManager
	if name == "SecurityError":
		from .file_system_manager import SecurityError
		return SecurityError
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
	return __all__