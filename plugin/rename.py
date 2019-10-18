import sublime
import sublime_plugin
from .core.registry import LspTextCommand
from .core.protocol import Request
from .core.edit import parse_workspace_edit
from .core.documents import get_document_position, get_position, is_at_word
try:
    from typing import List, Dict, Optional
    assert List and Dict and Optional
except ImportError:
    pass


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
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)

    def is_enabled(self, event: 'Optional[dict]' = None) -> bool:
        # TODO: check what kind of scope we're in.
        if self.has_client_with_capability('renameProvider'):
            return is_at_word(self.view, event)
        return False

    def input(self, args: dict) -> 'Optional[sublime_plugin.TextInputHandler]':
        if "new_name" not in args:
            return RenameSymbolInputHandler(self.view)
        else:
            return None

    def run(self, edit: sublime.Edit, new_name: str, event: 'Optional[dict]' = None) -> None:
        pos = get_position(self.view, event)
        position = get_document_position(self.view, pos)
        if position:
            self.request_rename(position, new_name)

    def request_rename(self, params: dict, new_name: str) -> None:
        client = self.client_with_capability('renameProvider')
        if client:
            params["newName"] = new_name
            client.send_request(Request.rename(params), self.handle_response)

    def handle_response(self, response: 'Optional[Dict]') -> None:
        window = self.view.window()
        if window:
            if response:
                changes = parse_workspace_edit(response)
                window.run_command('lsp_apply_workspace_edit',
                                   {'changes': changes})
            else:
                window.status_message('No rename edits returned')

    def want_event(self) -> bool:
        return True
