__all__ = ["Command", "ProcessingNode"]

def __getattr__(name: str):
	if name == "Command":
		from .command import Command
		return Command
	if name == "ProcessingNode":
		from .processing_node import ProcessingNode
		return ProcessingNode
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
	return __all__