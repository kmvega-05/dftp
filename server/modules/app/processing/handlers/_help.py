from server.modules.app.processing import Command
from server.modules.app.processing.cmd_help import COMMAND_HELP

def handle_help(cmd: Command, data : dict = None, processing_node = None):
    if cmd.require_args(0):
        commands = sorted(COMMAND_HELP.keys())
        msg = "Supported commands:\r\n" + " ".join(commands)
        return 214, msg, None

    if cmd.require_args(1):
        command_name = cmd.get_arg(0).upper()
        help_text = COMMAND_HELP.get(command_name)
        if not help_text:
            return 502, "Command not implemented.", None
        return 214, help_text, None

    return 501, "Syntax error in parameters.", None
