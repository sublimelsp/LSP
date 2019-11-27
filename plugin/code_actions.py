import sublime_plugin
import sublime

try:
    from typing import Any, List, Dict, Callable, Optional, Tuple, Union, Mapping
    from .core.sessions import Session
    from .core.protocol import Diagnostic
    from mypy_extensions import TypedDict
    CodeActionOrCommand = TypedDict('CodeActionOrCommand', {
        'title': str,
        'command': 'Union[dict, str]',
        'edit': dict
    },
                                    total=False)
    CodeActionsResponse = Optional[List[CodeActionOrCommand]]
    CodeActionsByConfigName = Dict[str, List[CodeActionOrCommand]]
    assert Any and List and Dict and Callable and Optional and Session and Tuple and Diagnostic and Union and Mapping
except ImportError:
    pass

from .core.registry import LspTextCommand
from .core.protocol import Request, Point
from .diagnostics import filter_by_point, view_diagnostics
from .core.edit import parse_workspace_edit
from .core.url import filename_to_uri
from .core.views import region_to_range
from .core.registry import sessions_for_view, client_from_session
from .core.settings import settings


class CodeActionsAtLocation(object):

    def __init__(self, on_complete_handler: 'Callable[[CodeActionsByConfigName], None]') -> None:
        self._commands_by_config = {}  # type: CodeActionsByConfigName
        self._requested_configs = []  # type: List[str]
        self._on_complete_handler = on_complete_handler

    def collect(self, config_name: str) -> 'Callable[[CodeActionsResponse], None]':
        self._requested_configs.append(config_name)
        return lambda actions: self.store(config_name, actions)

    def store(self, config_name: str, actions: 'CodeActionsResponse') -> None:
        self._commands_by_config[config_name] = actions or []
        if len(self._requested_configs) == len(self._commands_by_config):
            self._on_complete_handler(self._commands_by_config)

    def deliver(self, recipient_handler: 'Callable[[CodeActionsByConfigName], None]') -> None:
        recipient_handler(self._commands_by_config)


class CodeActionsManager(object):
    """ Collects and caches code actions"""

    def __init__(self) -> None:
        self._requests = {}  # type: Dict[str, CodeActionsAtLocation]

    def request(self, view: sublime.View, point: int, actions_handler: 'Callable[[CodeActionsByConfigName], None]',
                diagnostics_by_config: 'Optional[Dict[str, List[Diagnostic]]]' = None) -> None:
        current_location = self.get_location_key(view, point)
        # debug("requesting actions for {}".format(current_location))
        if current_location in self._requests:
            self._requests[current_location].deliver(actions_handler)
        else:
            self._requests.clear()
            if diagnostics_by_config is None:
                diagnostics_by_config = filter_by_point(view_diagnostics(view), Point(*view.rowcol(point)))
            self._requests[current_location] = request_code_actions(view, point, actions_handler)

    def get_location_key(self, view: sublime.View, point: int) -> str:
        return "{}#{}:{}".format(view.file_name(), view.change_count(), point)


actions_manager = CodeActionsManager()


def request_code_actions(view: sublime.View, point: int,
                         actions_handler: 'Callable[[CodeActionsByConfigName], None]') -> 'CodeActionsAtLocation':
    diagnostics_by_config = filter_by_point(view_diagnostics(view), Point(*view.rowcol(point)))
    return request_code_actions_with_diagnostics(view, diagnostics_by_config, point, actions_handler)


def request_code_actions_with_diagnostics(view: sublime.View, diagnostics_by_config: 'Dict[str, List[Diagnostic]]',
                                          point: int, actions_handler: 'Callable[[CodeActionsByConfigName], None]'
                                          ) -> 'CodeActionsAtLocation':

    actions_at_location = CodeActionsAtLocation(actions_handler)

    for session in sessions_for_view(view, point):

        if session.has_capability('codeActionProvider'):
            if session.config.name in diagnostics_by_config:
                point_diagnostics = diagnostics_by_config[session.config.name]
                file_name = view.file_name()
                relevant_range = point_diagnostics[0].range if point_diagnostics else region_to_range(
                    view,
                    view.sel()[0])
                if file_name:
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
                            actions_at_location.collect(session.config.name))
    return actions_at_location


class LspCodeActionBulbListener(sublime_plugin.ViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._stored_region = sublime.Region(-1, -1)
        self._actions = []  # type: List[CodeActionOrCommand]

    @classmethod
    def is_applicable(cls, _settings: dict) -> bool:
        if settings.show_code_actions_bulb:
            return True
        return False

    def on_selection_modified_async(self) -> None:
        self.hide_bulb()
        self.schedule_request()

    def schedule_request(self) -> None:
        current_region = self.view.sel()[0]
        if self._stored_region != current_region:
            self._stored_region = current_region
            sublime.set_timeout_async(lambda: self.fire_request(current_region), 800)

    def fire_request(self, current_region: 'sublime.Region') -> None:
        if current_region == self._stored_region:
            self._actions = []
            actions_manager.request(self.view, current_region.begin(), self.handle_responses)

    def handle_responses(self, responses: 'CodeActionsByConfigName') -> None:
        for _, items in responses.items():
            self._actions.extend(items)
        if len(self._actions) > 0:
            self.show_bulb()

    def show_bulb(self) -> None:
        region = self.view.sel()[0]
        flags = sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE
        self.view.add_regions('lsp_bulb', [region], 'markup.changed', 'Packages/LSP/icons/lightbulb.png', flags)

    def hide_bulb(self) -> None:
        self.view.erase_regions('lsp_bulb')


def is_command(command_or_code_action: 'CodeActionOrCommand') -> bool:
    command_field = command_or_code_action.get('command')
    return isinstance(command_field, str)


def execute_server_command(view: sublime.View, config_name: str, command: 'Mapping[str, Any]') -> None:
    session = next((session for session in sessions_for_view(view) if session.config.name == config_name), None)
    client = client_from_session(session)
    if client:
        client.send_request(
            Request.executeCommand(command),
            handle_command_response)


def handle_command_response(response: 'None') -> None:
    pass


def run_code_action_or_command(view: sublime.View, config_name: str,
                               command_or_code_action: 'CodeActionOrCommand') -> None:
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
        if isinstance(maybe_command, dict):
            execute_server_command(view, config_name, maybe_command)


class LspCodeActionsCommand(LspTextCommand):
    def is_enabled(self) -> bool:
        return self.has_client_with_capability('codeActionProvider')

    def run(self, edit: sublime.Edit) -> None:
        self.commands = []  # type: List[Tuple[str, str, CodeActionOrCommand]]
        self.commands_by_config = {}  # type: CodeActionsByConfigName
        actions_manager.request(self.view, self.view.sel()[0].begin(), self.handle_responses)

    def combine_commands(self) -> 'List[Tuple[str, str, CodeActionOrCommand]]':
        results = []
        for config, commands in self.commands_by_config.items():
            for command in commands:
                results.append((config, command['title'], command))
        return results

    def handle_responses(self, responses: 'CodeActionsByConfigName') -> None:
        self.commands_by_config = responses
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
