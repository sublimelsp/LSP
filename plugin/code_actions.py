from .core.edit import parse_workspace_edit
from .core.protocol import Diagnostic
from .core.protocol import Request, Point
from .core.registry import LspTextCommand
from .core.registry import LSPViewEventListener
from .core.registry import sessions_for_view, client_from_session
from .core.registry import windows
from .core.settings import settings
from .core.typing import Any, List, Dict, Callable, Optional, Union, Tuple, Mapping, TypedDict
from .core.url import filename_to_uri
from .core.views import entire_content_range, region_to_range
from .diagnostics import filter_by_point, view_diagnostics
import sublime
import sublime_plugin

CodeActionOrCommand = TypedDict('CodeActionOrCommand', {
    'title': str,
    'command': Union[dict, str],
    'edit': dict,
    'kind': Optional[str]
}, total=False)
CodeActionsResponse = Optional[List[CodeActionOrCommand]]
CodeActionsByConfigName = Dict[str, List[CodeActionOrCommand]]


class CodeActionsCollector(object):
    def __init__(self, on_complete_handler: Callable[[CodeActionsByConfigName], None]):
        self._on_complete_handler = on_complete_handler
        self._commands_by_config = {}  # type: CodeActionsByConfigName
        self._requested_configs = []  # type: List[str]
        self._all_requested = False

    def __enter__(self) -> 'CodeActionsCollector':
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self._all_requested = True
        self._notify_if_all_finished()

    def create_collector(self, config_name: str) -> Callable[[CodeActionsResponse], None]:
        self._requested_configs.append(config_name)
        return lambda actions: self._collect_response(config_name, actions)

    def _collect_response(self, config_name: str, actions: CodeActionsResponse) -> None:
        self._commands_by_config[config_name] = actions or []
        self._notify_if_all_finished()

    def _notify_if_all_finished(self) -> None:
        if self._all_requested and len(self._requested_configs) == len(self._commands_by_config):
            # Call back on the main thread
            sublime.set_timeout(lambda: self._on_complete_handler(self._commands_by_config))

    def get_actions(self) -> CodeActionsByConfigName:
        return self._commands_by_config


class CodeActionsManager(object):
    """ Collects and caches code actions"""

    def __init__(self) -> None:
        self._requests = {}  # type: Dict[str, CodeActionsCollector]

    def request(self, view: sublime.View,
                actions_handler: Callable[[CodeActionsByConfigName], None], point: int) -> None:
        current_location = self.get_location_key(view, point)
        # debug("requesting actions for {}".format(current_location))
        if current_location in self._requests:
            actions_handler(self._requests[current_location].get_actions())
        else:
            self._requests.clear()
            self._requests[current_location] = request_code_actions(view, actions_handler, point)

    def get_location_key(self, view: sublime.View, point: int) -> str:
        return "{}#{}:{}".format(view.file_name(), view.change_count(), point)


actions_manager = CodeActionsManager()


def request_code_actions(
    view: sublime.View,
    actions_handler: Callable[[CodeActionsByConfigName], None],
    point: int,
) -> CodeActionsCollector:
    actions_collector = CodeActionsCollector(actions_handler)
    with actions_collector:
        file_name = view.file_name()
        if file_name:
            diagnostics_by_config = filter_by_point(view_diagnostics(view), Point(*view.rowcol(point)))
            sessions = [session for session in sessions_for_view(view, 'codeActionProvider') if session.client]
            for session in sessions:
                config_name = session.config.name
                if config_name in diagnostics_by_config:
                    diagnostics = diagnostics_by_config[config_name]
                    request = Request.codeAction(_create_code_action_request_params(view, file_name, diagnostics))
                    session.client.send_request(request, actions_collector.create_collector(config_name))
    return actions_collector


def request_code_actions_on_save(
    view: sublime.View,
    actions_handler: Callable[[CodeActionsByConfigName], None],
    on_save_actions: Dict[str, bool]
) -> CodeActionsCollector:
    def filtering_collector(
        config_name: str,
        kinds: List[str],
        actions_collector: CodeActionsCollector
    ) -> Callable[[CodeActionsResponse], None]:
        """
        Filters actions returned from server so that only matching kinds are collected.

        Since older servers don't support the "context.only" property, they will return all
        actions regardless of what is requested.
        """
        def actions_filter(actions: CodeActionsResponse) -> List[CodeActionOrCommand]:
            return [a for a in (actions or []) if a.get('kind') in kinds]
        collector = actions_collector.create_collector(config_name)
        return lambda actions: collector(actions_filter(actions))

    actions_collector = CodeActionsCollector(actions_handler)
    with actions_collector:
        file_name = view.file_name()
        if file_name:
            sessions = [session for session in sessions_for_view(view, 'codeActionProvider') if session.client]
            for session in sessions:
                supported_kinds = session.get_capability('codeActionProvider.codeActionKinds')
                matching_kinds = get_matching_kinds(on_save_actions, supported_kinds or [])
                if matching_kinds:
                    params = _create_code_action_request_params(view, file_name, [], matching_kinds)
                    request = Request.codeAction(params)
                    session.client.send_request(
                        request, filtering_collector(session.config.name, matching_kinds, actions_collector))
    return actions_collector


def _create_code_action_request_params(
    view: sublime.View,
    file_name: str,
    diagnostics: List[Diagnostic],
    on_save_actions: Optional[List[str]] = None
) -> Dict:
    if on_save_actions:
        relevant_range = entire_content_range(view)
    else:
        relevant_range = diagnostics[0].range if diagnostics else region_to_range(view, view.sel()[0])
    params = {
        "textDocument": {
            "uri": filename_to_uri(file_name)
        },
        "range": relevant_range.to_lsp(),
        "context": {
            "diagnostics": list(diagnostic.to_lsp() for diagnostic in diagnostics)
        }
    }
    if on_save_actions:
        params['context']['only'] = on_save_actions
    return params


def get_matching_kinds(user_actions: Dict[str, bool], session_actions: List[str]) -> List[str]:
    """
    Filters user-enabled or disabled actions so that only ones matching the session actions
    are returned. Returned actions are those that are enabled and are not overridden by more
    specific disabled actions.

    Filtering only returns actions that exactly match ones supported by given session.
    If user has enabled a generic action that matches more specific session action
    (for example user's a.b matching session's a.b.c), then the more specific (a.b.c) must be
    returned as servers must receive only actions that they advertise support for.
    """
    matching_kinds = []
    for session_action in session_actions:
        enabled = False
        action_parts = session_action.split('.')
        for i in range(len(action_parts)):
            current_part = '.'.join(action_parts[0:i + 1])
            user_value = user_actions.get(current_part, None)
            if isinstance(user_value, bool):
                enabled = user_value
        if enabled:
            matching_kinds.append(session_action)
    return matching_kinds


class LspSaveCommand(sublime_plugin.TextCommand):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._fix_task = None  # type: Optional[CodeActionTask]

    def run(self, edit: sublime.Edit) -> None:
        if self._fix_task:
            self._fix_task.cancel()
        on_save_actions = self._get_code_actions_on_save(self.view.settings())
        if on_save_actions:
            self._fix_task = CodeActionTask(self.view, on_save_actions, self._trigger_native_save)
            self._fix_task.run()
        else:
            self._trigger_native_save()

    def _get_code_actions_on_save(self, view_settings: Union[dict, sublime.Settings]) -> Dict[str, bool]:
        view_code_actions = view_settings.get('lsp_code_actions_on_save') or {}
        code_actions = settings.lsp_code_actions_on_save.copy()
        code_actions.update(view_code_actions)
        allowed_code_actions = dict()
        for key, value in code_actions.items():
            if key.startswith('source.'):
                allowed_code_actions[key] = value
        return allowed_code_actions

    def _trigger_native_save(self) -> None:
        print('NATIVE SAVE')
        self._fix_task = None
        self.view.run_command('save', {"async": True})


class CodeActionTask():
    def __init__(self, view: sublime.View, on_save_actions: Dict[str, bool], on_done: Callable[[], None]) -> None:
        self._view = view
        self._manager = windows.lookup(view.window())
        self._on_save_actions = on_save_actions
        self._on_done = on_done
        self._completed = False
        self._canceled = False
        self._fix_iteration = 0

    def run(self) -> None:
        sublime.set_timeout(self._on_timeout, settings.code_action_on_save_timeout_ms)
        self._run_code_actions()

    def _run_code_actions(self) -> None:
        self._fix_iteration += 1
        if self._fix_iteration > 3:
            print('TOO MANY ITERATIONS. ABORTING.')
            self._on_complete()
            return
        self._manager.documents.purge_changes(self._view)
        request_code_actions_on_save(self._view, self._handle_response, self._on_save_actions)

    def _handle_response(self, responses: CodeActionsByConfigName) -> None:
        if self._canceled:
            return
        ran_code_action_or_command = False
        for config_name, code_actions in responses.items():
            if code_actions:
                print('CODE_ACTIONS (config: {})'.format(config_name), code_actions)
                for code_action in code_actions:
                    ran_code_action_or_command = True
                    run_code_action_or_command(self._view, config_name, code_action)
        if ran_code_action_or_command:
            self._run_code_actions()
        else:
            self._on_complete()

    def _on_timeout(self) -> None:
        if not self._completed and not self._canceled:
            print('TIMEOUT, ABORTING')
            self._canceled = True
            self._on_complete()

    def _on_complete(self) -> None:
        self._completed = True
        self._on_done()

    def cancel(self) -> None:
        self._canceled = True


class LspCodeActionBulbListener(LSPViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._stored_region = sublime.Region(-1, -1)
        self._actions = []  # type: List[CodeActionOrCommand]

    @classmethod
    def is_applicable(cls, _settings: dict) -> bool:
        return settings.show_code_actions_bulb

    def on_selection_modified_async(self) -> None:
        self.hide_bulb()
        self.schedule_request()

    def schedule_request(self) -> None:
        try:
            current_region = self.view.sel()[0]
        except IndexError:
            return
        if self._stored_region != current_region:
            self._stored_region = current_region
            sublime.set_timeout_async(lambda: self.fire_request(current_region), 800)

    def fire_request(self, current_region: sublime.Region) -> None:
        if current_region == self._stored_region:
            self._actions = []
            actions_manager.request(self.view, self.handle_responses, current_region.begin())

    def handle_responses(self, responses: CodeActionsByConfigName) -> None:
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


def is_command(command_or_code_action: CodeActionOrCommand) -> bool:
    command_field = command_or_code_action.get('command')
    return isinstance(command_field, str)


def execute_server_command(view: sublime.View, config_name: str, command: Mapping[str, Any]) -> None:
    session = next((session for session in sessions_for_view(view) if session.config.name == config_name), None)
    client = client_from_session(session)
    if client:
        client.send_request(
            Request.executeCommand(command),
            handle_command_response)


def handle_command_response(response: 'None') -> None:
    pass


def run_code_action_or_command(view: sublime.View, config_name: str,
                               command_or_code_action: CodeActionOrCommand) -> None:
    if is_command(command_or_code_action):
        execute_server_command(view, config_name, command_or_code_action)
    else:
        # CodeAction can have an edit and/or command.
        maybe_edit = command_or_code_action.get('edit')
        if maybe_edit:
            changes = parse_workspace_edit(maybe_edit)
            window = view.window()
            if changes and window:
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
        actions_manager.request(self.view, self.handle_responses, self.view.sel()[0].begin())

    def combine_commands(self) -> 'List[Tuple[str, str, CodeActionOrCommand]]':
        results = []
        for config, commands in self.commands_by_config.items():
            for command in commands:
                results.append((config, command['title'], command))
        return results

    def handle_responses(self, responses: CodeActionsByConfigName) -> None:
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
