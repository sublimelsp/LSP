from .core.clients import LspTextCommand
from .core.clients import client_for_view
from .core.documents import get_document_position, get_position, is_at_word


class LspSymbolRenameCommand(LspTextCommand):
    def __init__(self, view):
        super().__init__(view)

    def is_enabled(self, event=None):
        # TODO: check what kind of scope we're in.
        if self.has_client_with_capability('renameProvider'):
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
            client.send_request(client.request_class.rename(params), self.handle_response)

    def handle_response(self, response):
        if response:
            if 'changes' in response:
                changes = response.get('changes')
                if len(changes) > 0:
                    self.view.window().run_command('lsp_apply_workspace_edit',
                                                   {'changes': changes})
        else:
            self.view.window().status_message('No rename edits returned')

    def want_event(self):
        return True
