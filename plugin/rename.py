import sublime_plugin
from .core.registry import client_for_view, LspTextCommand
from .core.protocol import Request
from .core.edit import parse_workspace_edit
from .core.documents import get_document_position, get_position, is_at_word
try:
    from typing import List, Dict, Optional
    assert List and Dict and Optional
except ImportError:
    pass


class RenameSymbolInputHandler(sublime_plugin.TextInputHandler):
    def __init__(self, view):
        self.view = view

    def name(self):
        return "new_name"

    def placeholder(self):
        return self.get_current_symbol_name()

    def initial_text(self):
        return self.get_current_symbol_name()

    def validate(self, name):
        return len(name) > 0

    def get_current_symbol_name(self):
        pos = get_position(self.view)
        current_name = self.view.substr(self.view.word(pos))
        # Is this check necessary?
        if not current_name:
            current_name = ""
        return current_name


class LspSymbolRenameCommand(LspTextCommand):
    def __init__(self, view):
        super().__init__(view)

    def is_enabled(self, event=None):
        # TODO: check what kind of scope we're in.
        if self.has_client_with_capability('renameProvider'):
            return is_at_word(self.view, event)
        return False

    def input(self, args):
        if "new_name" not in args:
            return RenameSymbolInputHandler(self.view)
        else:
            return None

    def run(self, edit, new_name, event=None):
        pos = get_position(self.view, event)
        params = get_document_position(self.view, pos)

        self.request_rename(params, new_name)

    def request_rename(self, params, new_name) -> None:
        client = client_for_view(self.view)
        if client:
            params["newName"] = new_name
            client.send_request(Request.rename(params), self.handle_response)

    def handle_response(self, response: 'Optional[Dict]') -> None:
        if response:
            changes = parse_workspace_edit(response)
            self.view.window().run_command('lsp_apply_workspace_edit',
                                           {'changes': changes})
        else:
            self.view.window().status_message('No rename edits returned')

    def want_event(self):
        return True
