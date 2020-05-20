import sublime
from .core.protocol import Request
from .core.registry import LspTextCommand
from .core.rpc import Client
from .core.typing import List, Optional, Dict, Any
from .core.url import filename_to_uri


class LspExecuteCommand(LspTextCommand):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)

    def run(self,
            edit: sublime.Edit,
            command_name: Optional[str] = None,
            command_args: Optional[List[Any]] = None) -> None:
        client = self.client_with_capability('executeCommandProvider')
        if client and command_name:
            window = self.view.window()
            if window:
                window.status_message("Running command {}".format(command_name))
            self._send_command(client, command_name, self._expand_variables(command_args))

    def _expand_variables(self, command_args: List[Any]) -> List[Any]:
        for i, arg in enumerate(command_args):
            if arg == "${file}":
                command_args[i] = filename_to_uri(self.view.file_name())
            elif arg == "${offset}":
                command_args[i] = self.view.sel()[-1].b
            elif arg == "${selection_begin}":
                command_args[i] = self.view.sel()[-1].begin()
            elif arg == "${selection_end}":
                command_args[i] = self.view.sel()[-1].end()
            elif arg == "${selection}":
                command_args[i] = self.view.substr(self.view.sel()[-1])
        return command_args

    def _handle_response(self, command: str, response: Optional[Any]) -> None:
        msg = "command {} completed".format(command)
        if response:
            msg += "with response: {}".format(response)

        sublime.message_dialog(msg)

    def _handle_error(self, command: str, error: Dict[str, Any]) -> None:
        msg = "command {} failed. Reason: {}".format(command, error.get("message", "none provided by server :("))
        sublime.message_dialog(msg)

    def _send_command(self, client: Client, command_name: str, command_args: Optional[List[Any]]) -> None:
        request = {
            "command": command_name,
            "arguments": command_args
        }
        client.send_request(Request.executeCommand(request),
                            lambda reponse: self._handle_response(command_name, reponse),
                            lambda error: self._handle_error(command_name, error))
