import sublime_plugin

from .core.configurations import is_supported_view
from .core.clients import client_for_view
from .core.protocol import Request
from .core.documents import get_document_position, get_position, is_at_word


class LspSymbolRenameCommand(sublime_plugin.TextCommand):
    def is_enabled(self, event=None):
        # TODO: check what kind of scope we're in.
        if is_supported_view(self.view):
            client = client_for_view(self.view)
            if client and client.has_capability('renameProvider'):
                return is_at_word(self.view, event)
        return False

    def run(self, edit, event=None):
        pos = get_position(self.view, event)
        params = get_document_position(self.view, pos)
        current_name = self.view.substr(self.view.word(pos))
        if not current_name:
            current_name = ""
        self.view.window().show_input_panel(
            "New name:", current_name, lambda text: self.request_rename(params, text),
            None, None)

    def request_rename(self, params, new_name):
        client = client_for_view(self.view)
        if client:
            params["newName"] = new_name
            client.send_request(Request.rename(params), self.handle_response)

    def handle_response(self, response):
        if 'changes' in response:
            changes = response.get('changes')
            if len(changes) > 0:
                self.view.window().run_command('lsp_apply_workspace_edit',
                                               {'changes': response})

    def want_event(self):
        return True
