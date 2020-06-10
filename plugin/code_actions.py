from .core.edit import parse_workspace_edit
from .core.protocol import Diagnostic
from .core.protocol import Range, Request, Point
from .core.registry import LspTextCommand
from .core.registry import LSPViewEventListener
from .core.registry import sessions_for_view
from .core.registry import windows
from .core.settings import settings
from .core.typing import Any, List, Dict, Callable, Optional, Union, Tuple, Mapping, TypedDict
from .core.views import code_action_params
from .core.views import make_link
from .core.windows import debounced
from .diagnostics import filter_by_point, view_diagnostics
from .diagnostics import filter_by_range
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


class CodeActionsCollector:
    """
    Collects code action responses from multiple sessions. Calls back the "on_complete_handler" with
    results when all responses are received.

    Usage example:

    with CodeActionsCollector() as collector:
        actions_manager.request_with_diagnostics(collector.create_collector('test_config'))
        actions_manager.request_with_diagnostics(collector.create_collector('another_config'))

    The "create_collector()" must only be called within the "with" context. Once the context is
    exited, the "on_complete_handler" will be called once all the created collectors receive the
    response (are called).
    """

    def __init__(self, on_complete_handler: Callable[[CodeActionsByConfigName], None]):
        self._on_complete_handler = on_complete_handler
        self._commands_by_config = {}  # type: CodeActionsByConfigName
        self._request_count = 0
        self._response_count = 0
        self._all_requested = False

    def __enter__(self) -> 'CodeActionsCollector':
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self._all_requested = True
        self._notify_if_all_finished()

    def create_collector(self, config_name: str) -> Callable[[CodeActionsResponse], None]:
        self._request_count += 1
        return lambda actions: self._collect_response(config_name, actions)

    def _collect_response(self, config_name: str, actions: CodeActionsResponse) -> None:
        self._response_count += 1
        self._commands_by_config[config_name] = actions or []
        self._notify_if_all_finished()

    def _notify_if_all_finished(self) -> None:
        if self._all_requested and self._request_count == self._response_count:
            # Call back on the main thread
            sublime.set_timeout(lambda: self._on_complete_handler(self._commands_by_config))

    def get_actions(self) -> CodeActionsByConfigName:
        return self._commands_by_config


class CodeActionsManager:
    """Manager for per-location caching of code action responses."""

    def __init__(self) -> None:
        self._point_cache = {}  # type: Dict[str, CodeActionsCollector]

    def request_for_point(
        self,
        view: sublime.View,
        actions_handler: Callable[[CodeActionsByConfigName], None],
        point: int
    ) -> None:
        current_location_key = "{}#{}:{}".format(view.file_name(), view.change_count(), point)
        if current_location_key in self._point_cache:
            actions_handler(self._point_cache[current_location_key].get_actions())
        else:
            self._point_cache.clear()
            diagnostics_by_config = filter_by_point(view_diagnostics(view), Point(*view.rowcol(point)))
            results = self.request_with_diagnostics(view, diagnostics_by_config, actions_handler)
            self._point_cache[current_location_key] = results

    def request_with_diagnostics(
        self,
        view: sublime.View,
        diagnostics_by_config: Dict[str, List[Diagnostic]],
        actions_handler: Callable[[CodeActionsByConfigName], None]
    ) -> CodeActionsCollector:
        """
        Requests code actions *only* for provided diagnostics. If session has no diagnostics then
        it will be skipped.
        """
        return self._request(view, diagnostics_by_config, True, actions_handler)

    def request_with_optional_diagnostics(
        self,
        view: sublime.View,
        diagnostics_by_config: Dict[str, List[Diagnostic]],
        actions_handler: Callable[[CodeActionsByConfigName], None]
    ) -> CodeActionsCollector:
        """
        Requests code actions with provided diagnostics included in the request. If there are
        no diagnostics for given session, the request will be made with empty diagnostics list.
        """
        return self._request(view, diagnostics_by_config, False, actions_handler)

    def request_on_save(
        self,
        view: sublime.View,
        actions_handler: Callable[[CodeActionsByConfigName], None],
        on_save_actions: Dict[str, bool]
    ) -> CodeActionsCollector:
        """
        Requests code actions on save.
        """
        return self._request(view, dict(), False, actions_handler, on_save_actions)

    def _request(
        self,
        view: sublime.View,
        diagnostics_by_config: Dict[str, List[Diagnostic]],
        only_with_diagnostics: bool,
        actions_handler: Callable[[CodeActionsByConfigName], None],
        on_save_actions: Optional[Dict[str, bool]] = None
    ) -> CodeActionsCollector:
        actions_collector = CodeActionsCollector(actions_handler)
        with actions_collector:
            file_name = view.file_name()
            if file_name:
                for session in sessions_for_view(view, 'codeActionProvider'):
                    if on_save_actions:
                        supported_kinds = session.get_capability('codeActionProvider.codeActionKinds')
                        matching_kinds = get_matching_kinds(on_save_actions, supported_kinds or [])
                        if matching_kinds:
                            params = code_action_params(view, file_name, [], matching_kinds)
                            request = Request.codeAction(params)
                            collect, onerror = self._filtering_collector(
                                session.config.name, matching_kinds, actions_collector)
                            session.send_request(request, collect, onerror)
                    else:
                        config_name = session.config.name
                        diagnostics = diagnostics_by_config.get(config_name, [])
                        if only_with_diagnostics and not diagnostics:
                            continue
                        params = code_action_params(view, file_name, diagnostics)
                        request = Request.codeAction(params)
                        session.send_request(request, actions_collector.create_collector(config_name))
        return actions_collector

    def _filtering_collector(
        self,
        config_name: str,
        kinds: List[str],
        actions_collector: CodeActionsCollector
    ) -> Tuple[Callable[[CodeActionsResponse], None], Callable[[Any], None]]:
        """
        Filters actions returned from the session so that only matching kinds are collected.

        Since older servers don't support the "context.only" property, these will return all
        actions that need to be filtered.
        """
        def actions_filter(actions: CodeActionsResponse) -> List[CodeActionOrCommand]:
            return [a for a in (actions or []) if a.get('kind') in kinds]
        collector = actions_collector.create_collector(config_name)
        return (
            lambda actions: collector(actions_filter(actions)),
            lambda error: collector([])
        )


actions_manager = CodeActionsManager()


def get_matching_kinds(user_actions: Dict[str, bool], session_actions: List[str]) -> List[str]:
    """
    Filters user-enabled or disabled actions so that only ones matching the session actions
    are returned. Returned actions are those that are enabled and are not overridden by more
    specific, disabled actions.

    Filtering only returns actions that exactly match the ones supported by given session.
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
    """
    A command used as a substitute for native save command. Runs code actions before triggering the
    native save command.
    """

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._task = None  # type: Optional[CodeActionOnSaveTask]

    def run(self, edit: sublime.Edit) -> None:
        if self._task:
            self._task.cancel()
        on_save_actions = self._get_code_actions_on_save(self.view.settings())
        if on_save_actions:
            self._task = CodeActionOnSaveTask(self.view, on_save_actions, self._trigger_native_save)
            self._task.run()
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
        self._task = None
        # Triggered from set_timeout to preserve original semantics of on_pre_save handling
        sublime.set_timeout(lambda: self.view.run_command('save', {"async": True}))


class CodeActionOnSaveTask:
    """
    The main task that requests code actions from sessions and runs them.

    The amount of time the task is allowed to run is defined by user-controlled setting. If the task
    runs longer, the native save will be triggered before waiting for results.
    """

    def __init__(self, view: sublime.View, on_save_actions: Dict[str, bool], on_done: Callable[[], None]) -> None:
        self._view = view
        self._manager = windows.lookup(view.window())
        self._on_save_actions = on_save_actions
        self._on_done = on_done
        self._completed = False
        self._canceled = False
        self._status_key = 'lsp_caos_timeout'

    def run(self) -> None:
        self._erase_view_status()
        sublime.set_timeout(self._on_timeout, settings.code_action_on_save_timeout_ms)
        self._request_code_actions()

    def _request_code_actions(self) -> None:
        self._manager.documents.purge_changes(self._view)
        actions_manager.request_on_save(self._view, self._handle_response, self._on_save_actions)

    def _handle_response(self, responses: CodeActionsByConfigName) -> None:
        if self._canceled:
            return
        document_version = self._view.change_count()
        for config_name, code_actions in responses.items():
            if code_actions:
                for code_action in code_actions:
                    run_code_action_or_command(self._view, config_name, code_action)
        if document_version != self._view.change_count():
            self._request_code_actions()
        else:
            self._on_complete()

    def _on_timeout(self) -> None:
        if not self._completed and not self._canceled:
            self._set_view_status('LSP: Timeout on processing code actions during saving')
            self._canceled = True
            self._on_complete()

    def _set_view_status(self, text: str) -> None:
        self._view.set_status(self._status_key, text)
        sublime.set_timeout(self._erase_view_status, 3000)

    def _erase_view_status(self) -> None:
        self._view.erase_status(self._status_key)

    def _on_complete(self) -> None:
        self._completed = True
        self._on_done()

    def cancel(self) -> None:
        self._canceled = True


class LspCodeActionsListener(LSPViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._stored_region = sublime.Region(-1, -1)

    def on_selection_modified_async(self) -> None:
        self.clear_annotations()
        try:
            current_region = self.view.sel()[0]
        except IndexError:
            return
        if self._stored_region != current_region:
            self._stored_region = current_region
            debounced(
                lambda: self.fire_request(current_region), 800,
                lambda: self._stored_region == current_region, async_thread=True)

    def fire_request(self, current_region: sublime.Region) -> None:
        view = self.view
        stored_range = Range(Point(*view.rowcol(self._stored_region.begin())),
                             Point(*view.rowcol(self._stored_region.end())))
        diagnostics_by_config = filter_by_range(view_diagnostics(view), stored_range)
        actions_manager.request_with_optional_diagnostics(view, diagnostics_by_config, self.handle_responses)

    def handle_responses(self, responses: CodeActionsByConfigName) -> None:
        action_count = sum(map(len, responses.values()))
        if action_count > 0:
            self.show_annotations(action_count)

    def show_annotations(self, action_count: int) -> None:
        suffix = 's' if action_count > 1 else ''
        code_actions_link = make_link('subl:lsp_code_actions', '{} code action{}'.format(action_count, suffix))
        self.view.add_regions('lsp_action_annotations', [self._stored_region],
                              flags=sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE,
                              annotations=["<div class=\"actions\">{}</div>".format(code_actions_link)],
                              annotation_color='#2196F3')

    def clear_annotations(self) -> None:
        self.view.erase_regions('lsp_action_annotations')


def is_command(command_or_code_action: CodeActionOrCommand) -> bool:
    command_field = command_or_code_action.get('command')
    return isinstance(command_field, str)


def execute_server_command(view: sublime.View, config_name: str, command: Mapping[str, Any]) -> None:
    session = next((session for session in sessions_for_view(view) if session.config.name == config_name), None)
    if session:
        session.send_request(
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

    capability = 'codeActionProvider'

    def run(self, edit: sublime.Edit, event: Optional[dict] = None) -> None:
        self.commands = []  # type: List[Tuple[str, str, CodeActionOrCommand]]
        self.commands_by_config = {}  # type: CodeActionsByConfigName
        view = self.view
        try:
            region = view.sel()[0]
        except IndexError:
            return
        selection_range = Range(Point(*view.rowcol(region.begin())), Point(*view.rowcol(region.end())))
        diagnostics_by_config = filter_by_range(view_diagnostics(view), selection_range)
        actions_manager.request_with_optional_diagnostics(view, diagnostics_by_config, self.handle_responses)

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
