import sublime_plugin
import sublime

try:
    from typing import Any, List, Dict, Callable, Optional
    assert Any and List and Dict and Callable and Optional
except ImportError:
    pass

from .core.registry import client_for_view, LspTextCommand
from .core.protocol import Request
from .core.diagnostics import get_point_diagnostics
from .core.url import filename_to_uri
from .core.views import region_to_range
from .core.helpers import debounce
from .core.registry import session_for_view
from .core.settings import settings


class CodeAction:
    def __init__(self, view: 'sublime.View') -> None:
        self.view = view

    def send_request(self, on_response_recieved: 'Optional[Callable]' = None):
        """ callback - hook with response as the first argument. """
        session = session_for_view(self.view)
        if not session or not session.has_capability('codeActionProvider'):
            # the server doesn't support code actions, just return
            return

        params = self._get_code_action_params()
        session.client.send_request(
            Request.codeAction(params),
            lambda response: self._handle_response(response, on_response_recieved))

    def _handle_response(self, response, callback: 'Optional[Callable]' = None) -> None:
        code_action = CodeAction(self.view)
        if settings.show_bulb:
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
    @classmethod
    def is_applicable(cls, _settings):
        if settings.show_bulb:
            return True
        return False

    def on_selection_modified_async(self):
        self.fire_request()

    def on_modified_async(self):
        self.handle_modified_async()

    @debounce(0.8)
    def handle_modified_async(self):
        self.fire_request()

    @debounce(0.5)
    def fire_request(self):
        self.view.run_command('lsp_update_code_actions')


class LspUpdateCodeActionsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.code_action = CodeAction(self.view)
        self.code_action.send_request()


class LspCodeActionsCommand(LspTextCommand):
    def is_enabled(self):
        return self.has_client_with_capability('codeActionProvider')

    def run(self, edit):
        self.commands = []  # type: List[Dict]

        self.code_action = CodeAction(self.view)
        self.code_action.send_request(self.handle_response)

    def get_titles(self):
        ''' Return a list of all command titles. '''
        titles = []
        for command in self.commands:
            titles.append(command.get('title'))  # TODO parse command and arguments
        return titles

    def handle_response(self, response: 'List[Dict]') -> None:
        self.commands = response
        self.show_popup_menu()

    def show_popup_menu(self) -> None:
        if len(self.commands) > 0:
            self.view.show_popup_menu(self.get_titles(), self.handle_select)
        else:
            self.view.show_popup('No actions available', sublime.HIDE_ON_MOUSE_MOVE_AWAY)

    def handle_select(self, index: int) -> None:
        if index > -1:
            client = client_for_view(self.view)
            if client:
                client.send_request(
                    Request.executeCommand(self.commands[index]),
                    self.handle_command_response)

    def handle_command_response(self, response):
        pass
