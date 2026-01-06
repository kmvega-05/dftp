"""
Core FTP Client logic.
Includes connection managers, parser, and command handler.
"""

__all__ = [
    "ControlConnectionManager",
    "DataConnectionManager",
    "ClientCommandHandler",
    "Parser",
    "MessageStructure"
]

def __getattr__(name: str):
    if name == "ControlConnectionManager":
        from .connection import ControlConnectionManager
        return ControlConnectionManager
    if name == "DataConnectionManager":
        from .data_connection import DataConnectionManager
        return DataConnectionManager
    if name == "ClientCommandHandler":
        from .commands import ClientCommandHandler
        return ClientCommandHandler
    if name == "Parser":
        from .parser import Parser
        return Parser
    if name == "MessageStructure":
        from .parser import MessageStructure
        return MessageStructure
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
    return __all__
