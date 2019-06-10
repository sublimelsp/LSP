import sublime_plugin
import sublime

try:
    from typing import Any, List, Dict, Callable, Optional
    assert Any and List and Dict and Callable and Optional
except ImportError:
    pass

from .core.registry import client_for_view, LspTextCommand
from .core.protocol import Request
from .diagnostics import get_point_diagnostics
from .core.edit import parse_workspace_edit
from .core.url import filename_to_uri
from .core.views import region_to_range
from .core.registry import session_for_view
from .core.settings import settings


def send_code_action_request(view, on_response_recieved: 'Callable'):
    session = session_for_view(view)
    if not session or not session.has_capability('codeActionProvider'):
        # the server doesn't support code actions, just return
        return

    region = view.sel()[0]
    pos = region.begin()
    point_diagnostics = get_point_diagnostics(view, pos)
    params = {
        "textDocument": {
            "uri": filename_to_uri(view.file_name())
        },
        "range": region_to_range(view, region).to_lsp(),
        "context": {
            "diagnostics": list(diagnostic.to_lsp() for diagnostic in point_diagnostics)
        }
    }
    session.client.send_request(
        Request.codeAction(params),
        lambda response: on_response_recieved(response))


class LspCodeActionBulbListener(sublime_plugin.ViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._stored_point = -1

    @classmethod
    def is_applicable(cls, _settings):
        if settings.show_code_actions_bulb:
            return True
        return False

    def on_selection_modified_async(self):
        self.hide_bulb()
        self.schedule_request()

    def schedule_request(self):
        current_point = self.view.sel()[0].begin()
        if self._stored_point != current_point:
            self._stored_point = current_point
            sublime.set_timeout_async(lambda: self.fire_request(current_point), 800)

    def fire_request(self, current_point: int) -> None:
        if current_point == self._stored_point:
            send_code_action_request(self.view, self.handle_response)

    def handle_response(self, response) -> None:
        if settings.show_code_actions_bulb:
            if len(response) > 0:
                self.show_bulb()
            else:
                self.hide_bulb()

    def show_bulb(self) -> None:
        region = self.view.sel()[0]
        flags = sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE
        self.view.add_regions('lsp_bulb', [region], 'markup.changed', 'Packages/LSP/icons/lightbulb.png', flags)

    def hide_bulb(self) -> None:
        self.view.erase_regions('lsp_bulb')


def is_command(command_or_code_action: dict) -> bool:
    command_field = command_or_code_action.get('command')
    return isinstance(command_field, str)


class LspCodeActionsCommand(LspTextCommand):
    def is_enabled(self):
        return self.has_client_with_capability('codeActionProvider')

    def run(self, edit):
        self.commands = []  # type: List[Dict]

        send_code_action_request(self.view, self.handle_response)

    def get_titles(self):
        ''' Return a list of all command titles. '''
        titles = []
        for command in self.commands:
            titles.append(command.get('title'))  # TODO parse command and arguments
        return titles

    def handle_response(self, response: 'Optional[List[Dict]]') -> None:
        self.commands = response or []
        self.show_popup_menu()

    def show_popup_menu(self) -> None:
        if len(self.commands) > 0:
            self.view.show_popup_menu(self.get_titles(), self.handle_select)
        else:
            self.view.show_popup('No actions available', sublime.HIDE_ON_MOUSE_MOVE_AWAY)

    def handle_select(self, index: int) -> None:
        if index > -1:

            selected = self.commands[index]
            if is_command(selected):
                self.run_command(selected)
            else:
                # CodeAction can have an edit and/or command.
                maybe_edit = selected.get('edit')
                if maybe_edit:
                    changes = parse_workspace_edit(maybe_edit)
                    self.view.window().run_command("lsp_apply_workspace_edit", {'changes': changes})
                maybe_command = selected.get('command')
                if maybe_command:
                    self.run_command(maybe_command)

    def run_command(self, command) -> None:
        client = client_for_view(self.view)
        if client:
            client.send_request(
                Request.executeCommand(command),
                self.handle_command_response)

    def handle_command_response(self, response):
        pass
