import sublime
from .core.registry import client_for_view, LspTextCommand
from .core.settings import client_configs
from .core.protocol import Request
from .core.logging import debug

try:
    from typing import List, Optional, Dict, Any
    assert List and Optional and Dict and Any
except ImportError:
    pass


class LspExecuteCommand(LspTextCommand):
    def __init__(self, view):
        super().__init__(view)

    def run(self, lsp_command) -> None:
        self._commands = []   # type: List[str]
        for config in client_configs.all:
            if config.commands:
                self._commands.extend(config.commands)

        if len(self._commands) > 0:
            self.view.window().show_quick_panel(self._commands, self._on_done)

    def _handle_response(self, command: str, response: 'Optional[Any]') -> None:
        debug("response for command {}: {}".format(command, response))
        pass

    def _handle_error(self, command: str, error: 'Dict[str, Any]') -> None:
        msg = "command {} failed. Reason: {}".format(command, error.get("message", "none provided by server :("))
        self.view.show_popup(msg, sublime.HIDE_ON_MOUSE_MOVE_AWAY)

    def _on_done(self, index: int) -> None:
        if index > -1:
            command = self._commands[index]
            client = client_for_view(self.view)
            if client:
                request = {
                    "command": command
                }
                client.send_request(Request.executeCommand(request),
                                    lambda reponse: self._handle_response(command, reponse),
                                    lambda error: self._handle_error(command, error))
