import sublime
from .core.protocol import Error
from .core.protocol import ExecuteCommandParams
from .core.registry import LspTextCommand
from .core.registry import windows
from .core.typing import List, Optional, Any
from .core.views import uri_from_view, offset_to_point, region_to_range, text_document_identifier


class LspExecuteCommand(LspTextCommand):

    def run(self,
            edit: sublime.Edit,
            command_name: Optional[str] = None,
            command_args: Optional[List[Any]] = None,
            session_name: Optional[str] = None,
            event: Optional[dict] = None) -> None:
        # Handle VSCode-specific command for triggering AC/sighelp
        if command_name == "editor.action.triggerSuggest":
            # Triggered from set_timeout as suggestions popup doesn't trigger otherwise.
            return sublime.set_timeout(lambda: self.view.run_command("auto_complete"))
        if command_name == "editor.action.triggerParameterHints":

            def run_async() -> None:
                listener = windows.listener_for_view(self.view)
                if listener:
                    listener.do_signature_help_async(manual=False)

            return sublime.set_timeout_async(run_async)
        session = self.session_by_name(session_name if session_name else self.session_name)
        if session and command_name:
            params = {"command": command_name}  # type: ExecuteCommandParams
            if command_args:
                params["arguments"] = self._expand_variables(command_args)

            def handle_response(response: Any) -> None:
                assert command_name
                if isinstance(response, Error):
                    sublime.message_dialog("command {} failed. Reason: {}".format(command_name, str(response)))
                    return
                msg = "command {} completed".format(command_name)
                if response:
                    msg += "with response: {}".format(response)
                window = self.view.window()
                if window:
                    window.status_message(msg)

            session.execute_command(params, progress=True).then(handle_response)

    def _expand_variables(self, command_args: List[Any]) -> List[Any]:
        view = self.view  # type: sublime.View
        region = view.sel()[0]
        for i, arg in enumerate(command_args):
            if arg in ["$document_id", "${document_id}"]:
                command_args[i] = text_document_identifier(view)
            elif arg in ["$file_uri", "${file_uri}"]:
                command_args[i] = uri_from_view(view)
            elif arg in ["$selection", "${selection}"]:
                command_args[i] = view.substr(region)
            elif arg in ["$offset", "${offset}"]:
                command_args[i] = region.b
            elif arg in ["$selection_begin", "${selection_begin}"]:
                command_args[i] = region.begin()
            elif arg in ["$selection_end", "${selection_end}"]:
                command_args[i] = region.end()
            elif arg in ["$position", "${position}"]:
                command_args[i] = offset_to_point(view, region.b).to_lsp()
            elif arg in ["$range", "${range}"]:
                command_args[i] = region_to_range(view, region).to_lsp()
        window_variables = view.window().extract_variables() if view.window() else {}
        return sublime.expand_variables(command_args, window_variables)
