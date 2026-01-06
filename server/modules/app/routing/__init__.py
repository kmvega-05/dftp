__all__ = ["ClientSession", "RoutingNode"]

def __getattr__(name: str):
	if name == "ClientSession":
		from .client_session.client_session import ClientSession
		return ClientSession
	if name == "RoutingNode":
		from .routing_node import RoutingNode
		return RoutingNode
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
	return __all__