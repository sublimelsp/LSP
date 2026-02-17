from __future__ import annotations

from ..protocol import ExecuteCommandParams
from .core.logging import debug
from .core.protocol import Error
from .core.registry import LspTextCommand
from .core.views import first_selection_region
from .core.views import offset_to_point
from .core.views import region_to_range
from .core.views import text_document_identifier
from .core.views import text_document_position_params
from .core.views import uri_from_view
from .core.views import versioned_text_document_identifier
from typing import Any
import sublime


class LspExecuteCommand(LspTextCommand):
    """
    Helper command for triggering workspace/executeCommand requests.
    """

    def run(self,
            edit: sublime.Edit,
            command_name: str | None = None,
            command_args: list[Any] | None = None,
            session_name: str | None = None,
            event: dict | None = None) -> None:
        session = self.session_by_name(session_name if session_name else self.session_name)
        if session and command_name:
            params: ExecuteCommandParams = {"command": command_name}
            if command_args:
                params["arguments"] = self._expand_variables(command_args)

            def handle_response(response: Any) -> None:
                assert command_name
                if isinstance(response, Error):
                    self.handle_error_async(response, command_name)
                    return
                self.handle_success_async(response, command_name)

            session.execute_command(params, progress=True, view=self.view).then(handle_response)

    def handle_success_async(self, result: Any, command_name: str) -> None:
        """
        Override this method to handle successful response to workspace/executeCommand.

        :param result: The result returned from the server.
        :param command_name: The name of the command that was executed.
        """
        msg = f"command {command_name} completed"
        if window := self.view.window():
            window.status_message(msg)

    def handle_error_async(self, error: Error, command_name: str) -> None:
        """
        Override this method to handle failed response to workspace/executeCommand.

        :param error: The Error object.
        :param command_name: The name of the command that was executed.
        """
        msg = f"command {command_name} failed: {str(error)}"
        debug(msg)
        if window := self.view.window():
            window.status_message(msg)

    def _expand_variables(self, command_args: list[Any]) -> list[Any]:
        view = self.view
        region = first_selection_region(view)
        for i, arg in enumerate(command_args):
            if arg in ["$document_id", "${document_id}"]:
                command_args[i] = text_document_identifier(view)
            elif arg in ["$versioned_document_id", "${versioned_document_id}"]:
                command_args[i] = versioned_text_document_identifier(view, view.change_count())
            elif arg in ["$file_uri", "${file_uri}"]:
                command_args[i] = uri_from_view(view)
            elif region is not None:
                if arg in ["$selection", "${selection}"]:
                    command_args[i] = view.substr(region)
                elif arg in ["$offset", "${offset}"]:
                    command_args[i] = region.b
                elif arg in ["$selection_begin", "${selection_begin}"]:
                    command_args[i] = region.begin()
                elif arg in ["$selection_end", "${selection_end}"]:
                    command_args[i] = region.end()
                elif arg in ["$position", "${position}"]:
                    command_args[i] = offset_to_point(view, region.b).to_lsp()
                elif arg in ["$line", "${line}"]:
                    command_args[i] = offset_to_point(view, region.b).row
                elif arg in ["$character", "${character}"]:
                    command_args[i] = offset_to_point(view, region.b).col
                elif arg in ["$range", "${range}"]:
                    command_args[i] = region_to_range(view, region)
                elif arg in ["$text_document_position", "${text_document_position}"]:
                    command_args[i] = text_document_position_params(view, region.b)
        window = view.window()
        window_variables = window.extract_variables() if window else {}
        return sublime.expand_variables(command_args, window_variables)
