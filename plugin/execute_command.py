import sublime
from .core.protocol import Request
from .core.registry import LspTextCommand
from .core.sessions import Session
from .core.typing import List, Optional, Dict, Any
from .core.views import uri_from_view, offset_to_point, region_to_range


class LspExecuteCommand(LspTextCommand):

    capability = 'executeCommandProvider'

    def run(self,
            edit: sublime.Edit,
            command_name: Optional[str] = None,
            command_args: Optional[List[Any]] = None,
            event: Optional[dict] = None) -> None:
        # Handle VSCode-specific command for triggering suggestions popup.
        if command_name == "editor.action.triggerSuggest":
            # Triggered from set_timeout as suggestions popup doesn't trigger otherwise.
            sublime.set_timeout(lambda: self.view.run_command("auto_complete"))
            return
        session = self.best_session(self.capability)
        if session and command_name:
            window = self.view.window()
            if window:
                window.status_message("Running command {}".format(command_name))
            if command_args:
                self._expand_variables(command_args)
            self._send_command(session, command_name, command_args)

    def _expand_variables(self, command_args: List[Any]) -> None:
        region = self.view.sel()[0]
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
                command_args[i] = offset_to_point(self.view, region.b).to_lsp()
            elif arg in ["$range", "${range}"]:
                command_args[i] = region_to_range(self.view, region).to_lsp()

    def _handle_response(self, command: str, response: Optional[Any]) -> None:
        msg = "command {} completed".format(command)
        if response:
            msg += "with response: {}".format(response)

        window = self.view.window()
        if window:
            window.status_message(msg)

    def _handle_error(self, command: str, error: Dict[str, Any]) -> None:
        msg = "command {} failed. Reason: {}".format(command, error.get("message", "none provided by server :("))
        sublime.message_dialog(msg)

    def _send_command(self, session: Session, command_name: str, command_args: Optional[List[Any]]) -> None:
        request = {"command": command_name, "arguments": command_args} if command_args else {"command": command_name}
        session.send_request(Request.executeCommand(request),
                             lambda reponse: self._handle_response(command_name, reponse),
                             lambda error: self._handle_error(command_name, error))
