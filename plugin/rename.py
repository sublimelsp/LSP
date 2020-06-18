import sublime
import sublime_plugin
from .core.edit import parse_workspace_edit
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.typing import Dict, Optional
from .core.views import text_document_position_params
from .documents import is_at_word


class RenameSymbolInputHandler(sublime_plugin.TextInputHandler):
    def __init__(self, view: sublime.View) -> None:
        self.view = view

    def name(self) -> str:
        return "new_name"

    def placeholder(self) -> str:
        return self.get_current_symbol_name()

    def initial_text(self) -> str:
        return self.get_current_symbol_name()

    def validate(self, name: str) -> bool:
        return len(name) > 0

    def get_current_symbol_name(self) -> str:
        pos = get_position(self.view)
        current_name = self.view.substr(self.view.word(pos))
        # Is this check necessary?
        if not current_name:
            current_name = ""
        return current_name


class LspSymbolRenameCommand(LspTextCommand):

    capability = 'renameProvider'

    def is_enabled(self, event: Optional[dict] = None) -> bool:
        # TODO: check what kind of scope we're in.
        return super().is_enabled(event) and is_at_word(self.view, event)

    def input(self, args: dict) -> Optional[sublime_plugin.TextInputHandler]:
        if "new_name" not in args:
            return RenameSymbolInputHandler(self.view)
        else:
            return None

    def run(self, edit: sublime.Edit, new_name: str, event: Optional[dict] = None) -> None:
        session = self.session(self.capability)
        if session:
            params = text_document_position_params(self.view, get_position(self.view, event))
            params["newName"] = new_name
            session.send_request(Request.rename(params), self.handle_response)

    def handle_response(self, response: Optional[Dict]) -> None:
        window = self.view.window()
        if window:
            if response:
                changes = parse_workspace_edit(response)
                window.run_command('lsp_apply_workspace_edit',
                                   {'changes': changes})
            else:
                window.status_message('No rename edits returned')
