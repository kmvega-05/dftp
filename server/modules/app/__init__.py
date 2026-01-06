__all__ = ["AuthNode", "RoutingNode", "ProcessingNode", "DataNode"]

def __getattr__(name: str):
	if name == "AuthNode":
		from .auth.auth_node import AuthNode
		return AuthNode
	if name == "RoutingNode":
		from .routing import RoutingNode
		return RoutingNode
	if name == "ProcessingNode":
		from .processing import ProcessingNode
		return ProcessingNode
	if name == "DataNode":
		from .data_node import DataNode
		return DataNode
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
	return __all__