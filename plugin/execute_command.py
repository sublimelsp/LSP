import sublime
from .core.registry import client_for_view, LspTextCommand
from .core.protocol import Request
from .core.rpc import Client

try:
    from typing import List, Optional, Dict, Any, Tuple
    assert List and Optional and Dict and Any, Tuple
except ImportError:
    pass


class LspExecuteCommand(LspTextCommand):
    def __init__(self, view):
        super().__init__(view)

    def run(self, edit, command_name=None, command_args=None) -> None:
        client = client_for_view(self.view)
        if client and command_name:
            self.view.window().status_message("Running command {}".format(command_name))
            self._send_command(client, command_name, command_args)

    def _handle_response(self, command: str, response: 'Optional[Any]') -> None:
        msg = "command {} completed".format(command)
        if response:
            msg += "with response: {}".format(response)

        sublime.message_dialog(msg)

    def _handle_error(self, command: str, error: 'Dict[str, Any]') -> None:
        msg = "command {} failed. Reason: {}".format(command, error.get("message", "none provided by server :("))
        sublime.message_dialog(msg)

    def _send_command(self, client: Client, command_name: str, command_args: 'Optional[List[Any]]') -> None:
        request = {
            "command": command_name,
            "arguments": command_args
        }
        client.send_request(Request.executeCommand(request),
                            lambda reponse: self._handle_response(command_name, reponse),
                            lambda error: self._handle_error(command_name, error))
