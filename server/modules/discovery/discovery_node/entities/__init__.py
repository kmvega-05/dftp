__all__ = ["RegisterTable", "ServiceRegister", "NodeType"]

def __getattr__(name: str):
	if name == "RegisterTable":
		from .register_table import RegisterTable
		return RegisterTable
	if name == "ServiceRegister":
		from .register_table import ServiceRegister
		return ServiceRegister
	if name == "NodeType":
		from .service_register import NodeType
		return NodeType
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
	return __all__