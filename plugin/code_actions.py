from LSP.plugin.core.registry import session_for_view
import sublime_plugin
import sublime

try:
    from typing import Any, List, Dict
    assert Any and List and Dict
except ImportError:
    pass

from .core.registry import client_for_view, LspTextCommand
from .core.protocol import Request
from .core.documents import get_position
from .core.diagnostics import get_point_diagnostics
from .core.url import filename_to_uri
from .core.views import region_to_range
from .core.helpers import debounce
from .core.events import global_events


class CodeAction:
    def __init__(self, view: sublime.View):
        self.view = view

    def send_request(self, callback: 'Optional[Callable]'=None):
        """ Send a code action request.
            callback - receives the response as the first argument """
        session = session_for_view(self.view)
        if not session or not session.has_capability('codeActionProvider'):
            return

        params = self._get_code_action_params()
        session.client.send_request(
            Request.codeAction(params),
            lambda response: self._handle_response(response, callback))

    def _handle_response(self, response: 'List[Dict]', callback: 'Optional[Callable]'=None) -> None:
        code_action = CodeAction(self.view)
        if len(response) > 0:
            code_action.show_bulb()
        else:
            code_action.hide_bulb()
        
        if callback is not None:
            callback(response)

    def show_bulb(self) -> None:
        region = self.view.sel()[0]
        flags = sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE
        self.view.add_regions('lsp_bulb', [region], 'markup.changed', 'Packages/LSP/icons/lightbulb.png', flags)

    def hide_bulb(self) -> None:
        self.view.erase_regions('lsp_bulb')

    def _get_code_action_params(self):
        region = self.view.sel()[0]
        pos = region.begin()
        point_diagnostics = get_point_diagnostics(self.view, pos)
        return {
            "textDocument": {
                "uri": filename_to_uri(self.view.file_name())
            },
            "range": region_to_range(self.view, region).to_lsp(),
            "context": {
                "diagnostics": list(diagnostic.to_lsp() for diagnostic in point_diagnostics)
            }
        }


class LspCodeActionListener(sublime_plugin.ViewEventListener):
    def on_selection_modified_async(self):
        self.handle_selection_modified()

    @debounce(0.3)
    def handle_selection_modified(self):
        code_action = CodeAction(self.view)
        code_action.send_request()


class LspCodeActionsCommand(LspTextCommand):
    def is_enabled(self):
        return self.has_client_with_capability('codeActionProvider')

    def run(self, edit):
        code_action = CodeAction(self.view)
        code_action.send_request(self.handle_response)

    def handle_response(self, response: 'List[Dict]') -> None:
        self.commands = response
        self.view.show_popup_menu(self.get_titles(), self.handle_select)

    def get_titles(self) -> 'List[str]':
        ''' Return a list of all command titles. '''
        titles = []
        for command in self.commands:
            titles.append(command.get('title'))  # TODO parse command and arguments
        return titles

    def handle_select(self, index: int) -> None:
        if index > -1:
            client = client_for_view(self.view)
            if client:
                client.send_request(
                    Request.executeCommand(self.commands[index]),
                    self.handle_command_response)

    def handle_command_response(self, response):
        pass


# Need to send CodeAction request after DidChange, so code actions stay up to date
# TODO: Find a better way to fire code action request after DidChange
def handle_did_change(view):
    @debounce(0.3)
    def update_code_actions():
        code_action.send_request()

    code_action = CodeAction(view)
    code_action.hide_bulb()
    update_code_actions()

global_events.subscribe('textDocument/didChange', handle_did_change)
