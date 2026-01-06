__all__ = ["TCPClient", "TCPServer"]

def __getattr__(name: str):
	if name == "TCPClient":
		from .tcp_client import TCPClient
		return TCPClient
	if name == "TCPServer":
		from .tcp_server import TCPServer
		return TCPServer
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
	return __all__