import sublime
import sublime_plugin
from .core.registry import client_for_view, LspTextCommand
from .core.settings import client_configs
from .core.protocol import Request
from .core.logging import debug
from .core.rpc import Client

try:
    from typing import List, Optional, Dict, Any, Tuple
    assert List and Optional and Dict and Any, Tuple
except ImportError:
    pass


class CommandNameInputHandler(sublime_plugin.ListInputHandler):
    def __init__(self, view):
        super(CommandNameInputHandler, self).__init__()
        self.view = view
        client = client_for_view(self.view)
        if client:
            self._commands = []  # type: List[Tuple[str, Tuple[str, Dict[str, Any]]]]
            for config in client_configs.all:
                for command in config.commands:
                    x = (command.name, (command.name, command.args))
                    self._commands.append(x)

    def list_items(self):
        return self._commands

    def placeholder(self):
        return self._commands[0]


class LspExecuteCommand(LspTextCommand):
    def __init__(self, view):
        super().__init__(view)

    def run(self, edit, command_name=None, command_args=None) -> None:
        client = client_for_view(self.view)
        if client and command_name:
            # for some reason ListInputHandler put all the values in the command_name arg as a list
            # so we have to detect that bellow
            if type(command_name) is list:
                name = command_name[0]
                args = command_name[1] if len(command_name) == 2 else dict()
                self._send_command(client, name, args)
            elif type(command_name) is str:
                self._send_command(client, command_name, command_args)

    def input(self, args):
        return None if 'foo' in args else CommandNameInputHandler(self.view)

    def _handle_response(self, command: str, response: 'Optional[Any]') -> None:
        debug("response for command {}: {}".format(command, response))
        pass

    def _handle_error(self, command: str, error: 'Dict[str, Any]') -> None:
        msg = "command {} failed. Reason: {}".format(command, error.get("message", "none provided by server :("))
        self.view.show_popup(msg, sublime.HIDE_ON_MOUSE_MOVE_AWAY)

    def _send_command(self, client: Client, command_name: str, command_args: 'Dict[str, Any]') -> None:
        request = {
            "command": command_name,
            "args": command_args
        }
        client.send_request(Request.executeCommand(request),
                            lambda reponse: self._handle_response(command_name, reponse),
                            lambda error: self._handle_error(command_name, error))
