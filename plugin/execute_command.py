import sublime
from .core.registry import client_for_view, LspTextCommand
from .core.protocol import Request
from .core.logging import debug
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
            self._send_command(client, command_name, command_args)

    def _handle_response(self, command: str, response: 'Optional[Any]') -> None:
        # if response:
        debug("response for command {}: {}".format(command, response))

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
