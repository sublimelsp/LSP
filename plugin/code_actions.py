import sublime_plugin
import sublime

try:
    from typing import Any, List, Dict, Callable, Optional, Tuple
    from .core.sessions import Session
    from .core.protocol import Diagnostic
    assert Any and List and Dict and Callable and Optional and Session and Tuple and Diagnostic
except ImportError:
    pass

from .core.registry import LspTextCommand
from .core.protocol import Request
from .diagnostics import point_diagnostics_by_config
from .core.edit import parse_workspace_edit
from .core.url import filename_to_uri
from .core.views import region_to_range
from .core.registry import sessions_for_view, client_from_session
from .core.settings import settings


def request_code_actions(view: sublime.View, point: int,
                         actions_handler: 'Callable[[str, Optional[List[Dict]]], None]') -> 'List[str]':
    diagnostics_by_config = point_diagnostics_by_config(view, point)
    return request_code_actions_with_diagnostics(view, diagnostics_by_config, point, actions_handler)


def request_code_actions_with_diagnostics(view: sublime.View, diagnostics_by_config: 'Dict[str, List[Diagnostic]]',
                                          point: int, actions_handler: 'Callable[[str, Optional[List[Dict]]], None]'
                                          ) -> 'List[str]':
    configs = []  # type: List[str]
    for session in sessions_for_view(view, point):

        def handle_response(response: 'Optional[List[Dict]]', config_name: str = session.config.name) -> None:
            actions_handler(config_name, response)

        if session.has_capability('codeActionProvider'):
            if session.config.name in diagnostics_by_config:
                point_diagnostics = diagnostics_by_config[session.config.name]
                file_name = view.file_name()
                relevant_range = point_diagnostics[0].range if point_diagnostics else region_to_range(
                    view,
                    view.sel()[0])
                if file_name:
                    configs.append(session.config.name)
                    params = {
                        "textDocument": {
                            "uri": filename_to_uri(file_name)
                        },
                        "range": relevant_range.to_lsp(),
                        "context": {
                            "diagnostics": list(diagnostic.to_lsp() for diagnostic in point_diagnostics)
                        }
                    }
                    if session.client:
                        session.client.send_request(
                            Request.codeAction(params),
                            handle_response)
    return configs


class LspCodeActionBulbListener(sublime_plugin.ViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._stored_point = -1

    @classmethod
    def is_applicable(cls, _settings: 'Any') -> bool:
        if settings.show_code_actions_bulb:
            return True
        return False

    def on_selection_modified_async(self) -> None:
        self.hide_bulb()
        self.schedule_request()

    def schedule_request(self) -> None:
        current_point = self.view.sel()[0].begin()
        if self._stored_point != current_point:
            self._stored_point = current_point
            sublime.set_timeout_async(lambda: self.fire_request(current_point), 800)

    def fire_request(self, current_point: int) -> None:
        if current_point == self._stored_point:
            request_code_actions(self.view, current_point, self.handle_response)

    def handle_response(self, config_name: str, response: 'Any') -> None:
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


def execute_server_command(view: sublime.View, config_name: str, command: dict) -> None:
    session = next((session for session in sessions_for_view(view) if session.config.name == config_name), None)
    client = client_from_session(session)
    if client:
        client.send_request(
            Request.executeCommand(command),
            handle_command_response)


def handle_command_response(response: 'Any') -> None:
    pass


def run_code_action_or_command(view: sublime.View, config_name: str, command_or_code_action: dict) -> None:
    if is_command(command_or_code_action):
        execute_server_command(view, config_name, command_or_code_action)
    else:
        # CodeAction can have an edit and/or command.
        maybe_edit = command_or_code_action.get('edit')
        if maybe_edit:
            changes = parse_workspace_edit(maybe_edit)
            window = view.window()
            if window:
                window.run_command("lsp_apply_workspace_edit", {'changes': changes})
        maybe_command = command_or_code_action.get('command')
        if maybe_command:
            execute_server_command(view, config_name, maybe_command)


class LspCodeActionsCommand(LspTextCommand):
    def is_enabled(self) -> bool:
        return self.has_client_with_capability('codeActionProvider')

    def run(self, edit: 'Any') -> None:
        self.commands = []  # type: List[Tuple[str, str, Dict]]
        self.commands_by_config = {}  # type: Dict[str, List[Dict]]
        self.requested_server_configs = request_code_actions(self.view,
                                                             self.view.sel()[0].begin(), self.handle_response)

    def combine_commands(self) -> 'List[Tuple[str, str, Dict]]':
        results = []
        for config, commands in self.commands_by_config.items():
            for command in commands:
                results.append((config, command['title'], command))
        return results

    def handle_response(self, config_name: str, response: 'Optional[List[Dict]]') -> None:
        self.commands_by_config[config_name] = response or []
        if len(self.requested_server_configs) == len(self.commands_by_config):
            self.commands = self.combine_commands()
            self.show_popup_menu()

    def show_popup_menu(self) -> None:
        if len(self.commands) > 0:
            self.view.show_popup_menu([command[1] for command in self.commands], self.handle_select)
        else:
            self.view.show_popup('No actions available', sublime.HIDE_ON_MOUSE_MOVE_AWAY)

    def handle_select(self, index: int) -> None:
        if index > -1:
            selected = self.commands[index]
            run_code_action_or_command(self.view, selected[0], selected[2])
