from .core.protocol import Error
from .core.protocol import ExecuteCommandParams
from .core.registry import LspTextCommand
from .core.types import ClientConfig
from .core.typing import List, Optional, Any
from .core.views import uri_from_view, offset_to_point, region_to_range, text_document_identifier
import sublime


class LspExecuteCommand(LspTextCommand):

    capability = 'executeCommandProvider'

    def run(self,
            edit: sublime.Edit,
            command_name: Optional[str] = None,
            command_args: Optional[List[Any]] = None,
            session_name: Optional[str] = None,
            event: Optional[dict] = None) -> None:
        session = self.session_by_name(session_name) if session_name else self.best_session(self.capability)
        if session and command_name:
            if command_args:
                self._expand_variables(session.config, command_args)
            params = {"command": command_name}  # type: ExecuteCommandParams
            if command_args:
                params["arguments"] = command_args

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

            session.execute_command(params).then(handle_response)

    def _expand_variables(self, config: ClientConfig, command_args: List[Any]) -> None:
        region = self.view.sel()[0]
        for i, arg in enumerate(command_args):
            if arg in ["$document_id", "${document_id}"]:
                command_args[i] = text_document_identifier(self.view, config)
            if arg in ["$file_uri", "${file_uri}"]:
                command_args[i] = uri_from_view(self.view, config)
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
