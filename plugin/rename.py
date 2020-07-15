import sublime
import sublime_plugin
from .core.edit import parse_workspace_edit
from .core.protocol import Range
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.typing import Any, Dict, Optional
from .core.views import range_to_region
from .core.views import text_document_position_params
from .documents import is_at_word


class RenameSymbolInputHandler(sublime_plugin.TextInputHandler):
    def __init__(self, view: sublime.View, placeholder: str) -> None:
        self.view = view
        self._placeholder = placeholder

    def name(self) -> str:
        return "new_name"

    def placeholder(self) -> str:
        if self._placeholder:
            return self._placeholder
        return self.get_current_symbol_name()

    def initial_text(self) -> str:
        return self.placeholder()

    def validate(self, name: str) -> bool:
        return len(name) > 0

    def get_current_symbol_name(self) -> str:
        pos = get_position(self.view)
        current_name = self.view.substr(self.view.word(pos))
        # Is this check necessary?
        if not current_name:
            current_name = ""
        return current_name


class LspRenameBasicCommand(LspTextCommand):

    capability = 'renameProvider'
    placeholder = ""

    def is_enabled(self, event: Optional[dict] = None) -> bool:
        # TODO: check what kind of scope we're in.
        return super().is_enabled(event) and is_at_word(self.view, event)

    def input(self, args: dict) -> Optional[sublime_plugin.TextInputHandler]:
        if "new_name" not in args:
            placeholder = self.placeholder
            self.placeholder = ""
            return RenameSymbolInputHandler(self.view, placeholder)
        else:
            return None

    def run(
        self,
        _: sublime.Edit,
        new_name: str,
        position: Optional[int] = None,
        event: Optional[dict] = None
    ) -> None:
        session = self.session(self.capability)
        if session:
            if position is None:
                position = get_position(self.view, event)
            params = text_document_position_params(self.view, position)
            params["newName"] = new_name
            session.send_request(Request.rename(params), self.handle_response)

    def handle_response(self, response: Optional[Dict]) -> None:
        window = self.view.window()
        if window:
            if response:
                changes = parse_workspace_edit(response)
                window.run_command('lsp_apply_workspace_edit', {'changes': changes})
            else:
                window.status_message('No rename edits returned')


class LspRenamePrepareCommand(LspTextCommand):
    capability = "renameProvider.prepareProvider"

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.event = None  # type: Optional[dict]

    def run(self, edit: sublime.Edit, event: Optional[dict] = None) -> None:
        session = self.session(self.capability)
        if session:
            params = text_document_position_params(self.view, get_position(self.view, event))
            request = Request("textDocument/prepareRename", params)
            session.send_request(request, self.on_result, self.on_error)
            self.event = event

    def on_result(self, response: Any) -> None:
        if response is None:
            sublime.error_message("The current selection cannot be renamed")
            return
        # It must be a dict at this point.
        if "placeholder" in response:
            LspRenameBasicCommand.placeholder = response["placeholder"]
            r = response["range"]
        else:
            LspRenameBasicCommand.placeholder = ""
            r = response
        args = {"event": self.event, "position": range_to_region(Range.from_lsp(r), self.view).a}
        self.view.run_command("lsp_rename_basic", args)

    def on_error(self, error: Any) -> None:
        sublime.error_message("Rename error: {}".format(error["message"]))


class LspSymbolRenameCommand(LspTextCommand):

    capability = 'renameProvider'

    def is_enabled(self, event: Optional[dict] = None) -> bool:
        if self.session("renameProvider.prepareProvider"):
            # The language server will tell us if the selection is on a valid token.
            return True
        # TODO: check what kind of scope we're in.
        return super().is_enabled(event) and is_at_word(self.view, event)

    def run(self, edit: sublime.Edit, event: Optional[dict] = None) -> None:
        session = self.session("renameProvider.prepareProvider")
        command = "lsp_rename_{}".format("prepare" if session else "basic")
        self.view.run_command(command, {"event": event})
