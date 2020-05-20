import sublime
from .core.protocol import Request
from .core.registry import LspTextCommand
from .core.rpc import Client
from .core.typing import List, Optional, Dict, Any
from .core.views import uri_from_view


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
            if command_args:
                command_args = self._expand_variables(command_args)
            self._send_command(client, command_name, command_args)

    def _expand_variables(self, command_args: List[Any]) -> List[Any]:
        region = self.view.sel()[-1]
        for i, arg in enumerate(command_args):
            if arg in ["$file_uri", "${file_uri}"]:
                command_args[i] = uri_from_view(self.view)
            elif arg in ["$selection", "${selection}"]:
                command_args[i] = self.view.substr(region)
            elif arg in ["$offset", "${offset}"]:
                command_args[i] = region.b
            elif arg in ["$selection_begin", "${selection_begin}"]:
                command_args[i] = region.begin()
            elif arg in ["$selection_end", "${selection_end}"]:
                command_args[i] = region.end()
            elif arg in ["$position", "${position}"]:
                position = self.view.rowcol(region.b)
                command_args[i] = {"line": position[0], "character": position[1]}
            elif arg in ["$range", "${range}"]:
                start = self.view.rowcol(region.begin())
                end = self.view.rowcol(region.end())
                command_args[i] = {
                    "start": {"line": start[0], "character": start[1]},
                    "end": {"line": end[0], "character": end[1]}
                }
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
        request = {"command": command_name, "arguments": command_args} if command_args else {"command": command_name}
        client.send_request(Request.executeCommand(request),
                            lambda reponse: self._handle_response(command_name, reponse),
                            lambda error: self._handle_error(command_name, error))
