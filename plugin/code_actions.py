from .core.promise import Promise
from .core.protocol import CodeAction
from .core.protocol import Command
from .core.protocol import Diagnostic
from .core.protocol import Error
from .core.protocol import Request
from .core.registry import LspTextCommand
from .core.registry import sessions_for_view
from .core.registry import windows
from .core.sessions import SessionBufferProtocol
from .core.settings import userprefs
from .core.typing import Any, List, Dict, Callable, Optional, Tuple, Union, Sequence
from .core.views import entire_content_region
from .core.views import first_selection_region
from .core.views import text_document_code_action_params
from .save_command import LspSaveCommand, SaveTask
import sublime

CodeActionOrCommand = Union[CodeAction, Command]
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
            # Call back on Sublime's async thread
            sublime.set_timeout_async(lambda: self._on_complete_handler(self._commands_by_config))

    def get_actions(self) -> CodeActionsByConfigName:
        return self._commands_by_config


class CodeActionsManager:
    """Manager for per-location caching of code action responses."""

    def __init__(self) -> None:
        self._response_cache = None  # type: Optional[Tuple[str, CodeActionsCollector]]

    def request_with_diagnostics_async(
        self,
        view: sublime.View,
        region: sublime.Region,
        session_buffer_diagnostics: Sequence[Tuple[SessionBufferProtocol, Sequence[Diagnostic]]],
        actions_handler: Callable[[CodeActionsByConfigName], None]
    ) -> None:
        """
        Requests code actions *only* for provided diagnostics. If session has no diagnostics then
        it will be skipped.
        """
        self._request_async(view, region, session_buffer_diagnostics, True, actions_handler)

    def request_for_region_async(
        self,
        view: sublime.View,
        region: sublime.Region,
        session_buffer_diagnostics: Sequence[Tuple[SessionBufferProtocol, Sequence[Diagnostic]]],
        actions_handler: Callable[[CodeActionsByConfigName], None],
        only_kinds: Optional[Dict[str, bool]] = None
    ) -> None:
        """
        Requests code actions with provided diagnostics and specified region. If there are
        no diagnostics for given session, the request will be made with empty diagnostics list.
        """
        self._request_async(view, region, session_buffer_diagnostics, False, actions_handler, only_kinds)

    def request_on_save(
        self,
        view: sublime.View,
        actions_handler: Callable[[CodeActionsByConfigName], None],
        on_save_actions: Dict[str, bool]
    ) -> None:
        """
        Requests code actions on save.
        """
        self._request_async(view, entire_content_region(view), [], False, actions_handler, on_save_actions)

    def _request_async(
        self,
        view: sublime.View,
        region: sublime.Region,
        session_buffer_diagnostics: Sequence[Tuple[SessionBufferProtocol, Sequence[Diagnostic]]],
        only_with_diagnostics: bool,
        actions_handler: Callable[[CodeActionsByConfigName], None],
        on_save_actions: Optional[Dict[str, bool]] = None
    ) -> None:
        use_cache = on_save_actions is None
        if use_cache:
            location_cache_key = "{}#{}:{}:{}".format(
                view.buffer_id(), view.change_count(), region, only_with_diagnostics)
            if self._response_cache:
                cache_key, cache_collector = self._response_cache
                if location_cache_key == cache_key:
                    sublime.set_timeout(lambda: actions_handler(cache_collector.get_actions()))
                    return
                else:
                    self._response_cache = None

        collector = CodeActionsCollector(actions_handler)
        with collector:
            file_name = view.file_name()
            if file_name:
                for session in sessions_for_view(view, 'codeActionProvider'):
                    if on_save_actions:
                        supported_kinds = session.get_capability('codeActionProvider.codeActionKinds')
                        matching_kinds = get_matching_kinds(on_save_actions, supported_kinds or [])
                        if matching_kinds:
                            params = text_document_code_action_params(
                                view, file_name, region, [], matching_kinds)
                            request = Request.codeAction(params, view)
                            session.send_request_async(
                                request, *filtering_collector(session.config.name, matching_kinds, collector))
                    else:
                        diagnostics = []  # type: Sequence[Diagnostic]
                        for sb, diags in session_buffer_diagnostics:
                            if sb.session == session:
                                diagnostics = diags
                                break
                        if only_with_diagnostics and not diagnostics:
                            continue
                        params = text_document_code_action_params(view, file_name, region, diagnostics)
                        request = Request.codeAction(params, view)
                        session.send_request_async(request, collector.create_collector(session.config.name))
        if use_cache:
            self._response_cache = (location_cache_key, collector)


def filtering_collector(
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
        return [a for a in (actions or []) if a.get('kind') in kinds]  # type: ignore

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


class CodeActionOnSaveTask(SaveTask):
    """
    The main task that requests code actions from sessions and runs them.

    The amount of time the task is allowed to run is defined by user-controlled setting. If the task
    runs longer, the native save will be triggered before waiting for results.
    """
    @classmethod
    def is_applicable(cls, view: sublime.View) -> bool:
        return bool(view.window()) and bool(cls._get_code_actions_on_save(view))

    @classmethod
    def _get_code_actions_on_save(cls, view: sublime.View) -> Dict[str, bool]:
        view_code_actions = view.settings().get('lsp_code_actions_on_save') or {}
        code_actions = userprefs().lsp_code_actions_on_save.copy()
        code_actions.update(view_code_actions)
        allowed_code_actions = dict()
        for key, value in code_actions.items():
            if key.startswith('source.'):
                allowed_code_actions[key] = value
        return allowed_code_actions

    def get_task_timeout_ms(self) -> int:
        return userprefs().code_action_on_save_timeout_ms

    def run_async(self) -> None:
        super().run_async()
        self._request_code_actions_async()

    def _request_code_actions_async(self) -> None:
        self._purge_changes_async()
        on_save_actions = self._get_code_actions_on_save(self._task_runner.view)
        actions_manager.request_on_save(self._task_runner.view, self._handle_response_async, on_save_actions)

    def _handle_response_async(self, responses: CodeActionsByConfigName) -> None:
        if self._cancelled:
            return
        document_version = self._task_runner.view.change_count()
        tasks = []  # type: List[Promise]
        for config_name, code_actions in responses.items():
            if code_actions:
                for session in self._task_runner.sessions('codeActionProvider'):
                    if session.config.name == config_name:
                        for code_action in code_actions:
                            tasks.append(session.run_code_action_async(code_action, progress=False))
                        break
        Promise.all(tasks).then(lambda _: self._on_code_actions_completed(document_version))

    def _on_code_actions_completed(self, previous_document_version: int) -> None:
        if previous_document_version != self._task_runner.view.change_count():
            # Give on_text_changed_async a chance to trigger.
            sublime.set_timeout_async(self._request_code_actions_async)
        else:
            self._on_complete()


LspSaveCommand.register_task(CodeActionOnSaveTask)


class LspCodeActionsCommand(LspTextCommand):

    capability = 'codeActionProvider'

    def run(
        self,
        edit: sublime.Edit,
        event: Optional[dict] = None,
        only_kinds: Optional[List[str]] = None,
        commands_by_config: Optional[CodeActionsByConfigName] = None
    ) -> None:
        self.commands = []  # type: List[Tuple[str, str, CodeActionOrCommand]]
        self.commands_by_config = {}  # type: CodeActionsByConfigName
        if commands_by_config:
            self.handle_responses_async(commands_by_config, run_first=True)
        else:
            view = self.view
            region = first_selection_region(view)
            if region is None:
                return
            listener = windows.listener_for_view(view)
            if not listener:
                return
            session_buffer_diagnostics, covering = listener.diagnostics_intersecting_async(region)
            dict_kinds = {kind: True for kind in only_kinds} if only_kinds else None
            actions_manager.request_for_region_async(
                view, covering, session_buffer_diagnostics, self.handle_responses_async, dict_kinds)

    def handle_responses_async(self, responses: CodeActionsByConfigName, run_first: bool = False) -> None:
        self.commands_by_config = responses
        self.commands = self.combine_commands()
        if len(self.commands) == 1 and run_first:
            self.handle_select(0)
        else:
            self.show_code_actions()

    def combine_commands(self) -> 'List[Tuple[str, str, CodeActionOrCommand]]':
        results = []
        for config, commands in self.commands_by_config.items():
            for command in commands:
                results.append((config, command['title'], command))
        return results

    def show_code_actions(self) -> None:
        if len(self.commands) > 0:
            items = [command[1] for command in self.commands]
            window = self.view.window()
            if window:
                window.show_quick_panel(items, self.handle_select, placeholder="Code action")
        else:
            self.view.show_popup('No actions available', sublime.HIDE_ON_MOUSE_MOVE_AWAY)

    def handle_select(self, index: int) -> None:
        if index > -1:

            def run_async() -> None:
                selected = self.commands[index]
                session = self.session_by_name(selected[0])
                if session:
                    name = session.config.name
                    session.run_code_action_async(selected[2], progress=True).then(
                        lambda resp: self.handle_response_async(name, resp))

            sublime.set_timeout_async(run_async)

    def handle_response_async(self, session_name: str, response: Any) -> None:
        if isinstance(response, Error):
            sublime.error_message("{}: {}".format(session_name, str(response)))
