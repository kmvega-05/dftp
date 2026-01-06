__all__ = ["NodeType", "DiscoveryNode", "LocationNode"]

def __getattr__(name: str):
	if name == "DiscoveryNode":
		from .discovery_node.discovery_node import DiscoveryNode
		return DiscoveryNode
	if name == "NodeType":
		from .discovery_node.entities.service_register import NodeType
		return NodeType
	if name == "LocationNode":
		from .location_node.location_node import LocationNode
		return LocationNode
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
	return __all__