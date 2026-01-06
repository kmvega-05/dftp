__all__ = ["CommunicationNode", "Message", "MessageType"]

def __getattr__(name: str):
	if name == "CommunicationNode":
		from .communication_node.communication_node import CommunicationNode
		return CommunicationNode
	if name == "Message":
		from .message.message import Message
		return Message
	if name == "MessageType":
		from .message.message_type import MessageType
		return MessageType
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
	return __all__