import sublime
from .core.registry import client_for_view, LspTextCommand
from .core.settings import client_configs
from .core.protocol import Request
from .core.logging import debug
from .core.rpc import Client

try:
    from typing import List, Optional, Dict, Any
    assert List and Optional and Dict and Any
except ImportError:
    pass


class LspExecuteCommand(LspTextCommand):
    def __init__(self, view):
        super().__init__(view)

    def run(self, edit, command_name: 'Optional[str]'=None, command_args: 'Dict[str, Any]'=dict()) -> None:
        client = client_for_view(self.view)
        if client:
            if command_name:
                self._send_command(client, command_name, command_args)
            else:
                self._command_names = []   # type: List[str]
                self._command_args = dict()   # type: Dict[str, Dict[str, Any]]
                for config in client_configs.all:
                    for command in config.commands:
                        self._command_names.append(command.name)
                        self._command_args[command.name] = command.args

                if len(self._command_names) > 0:
                    self.view.window().show_quick_panel(self._command_names, lambda i: self._on_done(client, i))

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

    def _on_done(self, client: Client, index: int) -> None:
        if index > -1:
            command = self._command_names[index]
            args = self._command_args.get(command, dict())
            self._send_command(client, command, args)
