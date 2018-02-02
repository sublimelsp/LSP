import sublime

try:
    from typing import Any, List
    assert Any and List
except ImportError:
    pass


from .core.clients import client_for_view
from .core.clients import LspTextCommand
from .core.protocol import Request, Range
from .core.documents import get_position
from .core.diagnostics import get_point_diagnostics
from .core.url import filename_to_uri


class LspCodeActionsCommand(LspTextCommand):
    def __init__(self, view):
        super(LspCodeActionsCommand, self).__init__(view, 'codeActionProvider')

    def run(self, edit, event=None):
        client = client_for_view(self.view)
        if client:
            pos = get_position(self.view, event)
            row, col = self.view.rowcol(pos)
            point_diagnostics = get_point_diagnostics(self.view, pos)
            params = {
                "textDocument": {
                    "uri": filename_to_uri(self.view.file_name())
                },
                "context": {
                    "diagnostics": list(diagnostic.to_lsp() for diagnostic in point_diagnostics)
                }
            }
            params["range"] = Range.from_region(self.view, self.view.sel()[0]).to_lsp()
            if event:  # if right-clicked, set cursor to menu position
                sel = self.view.sel()
                sel.clear()
                sel.add(sublime.Region(pos))

            client.send_request(Request.codeAction(params), self.handle_codeaction_response)

    def handle_codeaction_response(self, response):
        titles = []
        self.commands = response
        for command in self.commands:
            titles.append(
                command.get('title'))  # TODO parse command and arguments
        if len(self.commands) > 0:
            self.view.show_popup_menu(titles, self.handle_select)
        else:
            self.view.show_popup('No actions available', sublime.HIDE_ON_MOUSE_MOVE_AWAY)

    def handle_select(self, index):
        if index > -1:
            client = client_for_view(self.view)
            if client:
                client.send_request(
                    Request.executeCommand(self.commands[index]),
                    self.handle_command_response)

    def handle_command_response(self, response):
        pass

    def want_event(self):
        return True
