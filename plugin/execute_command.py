from .core.registry import client_for_view, LspTextCommand
from .core.settings import client_configs
from .core.protocol import Request

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

    def _handle_response(self, response: 'Optional[Any]') -> None:
        pass

    def _on_done(self, index: int) -> None:
        if index > -1:
            command = self._commands[index]
            client = client_for_view(self.view)
            if client:
                request = {
                    "command": command
                }
                client.send_request(Request.executeCommand(request), self._handle_response)
