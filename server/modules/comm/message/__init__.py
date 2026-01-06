__all__ = ["Message", "MessageType"]

def __getattr__(name: str):
	if name == "Message":
		from .message import Message
		return Message
	if name == "MessageType":
		from .message_type import MessageType
		return MessageType
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
	return __all__