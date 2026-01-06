__all__ = ["GossipNode"]

def __getattr__(name: str):
	if name == "GossipNode":
		from .gossip_node import GossipNode
		return GossipNode
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
	return __all__