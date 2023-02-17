from .core.promise import Promise
from .core.protocol import CodeAction
from .core.protocol import CodeActionKind
from .core.protocol import Command
from .core.protocol import Diagnostic
from .core.protocol import Error
from .core.protocol import Request
from .core.registry import LspTextCommand
from .core.registry import LspWindowCommand
from .core.registry import windows
from .core.sessions import AbstractViewListener
from .core.sessions import SessionBufferProtocol
from .core.settings import userprefs
from .core.typing import Any, List, Dict, Callable, Optional, Tuple, TypeGuard, Union, cast
from .core.views import entire_content_region
from .core.views import first_selection_region
from .core.views import format_code_actions_for_quick_panel
from .core.views import text_document_code_action_params
from .save_command import LspSaveCommand
from .save_command import SaveTask
from abc import ABCMeta
from abc import abstractmethod
from functools import partial
import sublime

ConfigName = str
CodeActionOrCommand = Union[CodeAction, Command]
CodeActionsByConfigName = Tuple[ConfigName, List[CodeActionOrCommand]]
MENU_ACTIONS_KINDS = [CodeActionKind.Refactor, CodeActionKind.Source]


def is_command(action: CodeActionOrCommand) -> TypeGuard[Command]:
    return isinstance(action.get('command'), str)


class CodeActionsManager:
    """Manager for per-location caching of code action responses."""

    def __init__(self) -> None:
        self._response_cache = None  # type: Optional[Tuple[str, Promise[List[CodeActionsByConfigName]]]]
        self.menu_actions_cache_key = None  # type: Optional[str]
        self.refactor_actions_cache = []  # type: List[Tuple[str, CodeAction]]
        self.source_actions_cache = []  # type: List[Tuple[str, CodeAction]]

    def request_for_region_async(
        self,
        view: sublime.View,
        region: sublime.Region,
        session_buffer_diagnostics: List[Tuple[SessionBufferProtocol, List[Diagnostic]]],
        only_kinds: Optional[List[CodeActionKind]] = None,
        manual: bool = False,
    ) -> Promise[List[CodeActionsByConfigName]]:
        """
        Requests code actions with provided diagnostics and specified region. If there are
        no diagnostics for given session, the request will be made with empty diagnostics list.
        """
        listener = windows.listener_for_view(view)
        if not listener:
            self.menu_actions_cache_key = None
            return Promise.resolve([])
        location_cache_key = None
        use_cache = not manual
        if use_cache:
            location_cache_key = "{}#{}:{}".format(view.buffer_id(), view.change_count(), region)
            if self._response_cache:
                cache_key, task = self._response_cache
                if location_cache_key == cache_key:
                    return task
                else:
                    self._response_cache = None
        elif only_kinds == MENU_ACTIONS_KINDS:
            self.menu_actions_cache_key = "{}#{}:{}".format(view.buffer_id(), view.change_count(), region)
            self.refactor_actions_cache.clear()
            self.source_actions_cache.clear()

        def request_factory(sb: SessionBufferProtocol) -> Optional[Request]:
            diagnostics = []  # type: List[Diagnostic]
            for diag_sb, diags in session_buffer_diagnostics:
                if diag_sb == sb:
                    diagnostics = diags
                    break
            params = text_document_code_action_params(view, region, diagnostics, only_kinds, manual)
            return Request.codeAction(params, view)

        def response_filter(sb: SessionBufferProtocol, actions: List[CodeActionOrCommand]) -> List[CodeActionOrCommand]:
            # Filter out non "quickfix" code actions unless "only_kinds" is provided.
            if only_kinds:
                code_actions = [cast(CodeAction, a) for a in actions if not is_command(a) and not a.get('disabled')]
                if manual and only_kinds == MENU_ACTIONS_KINDS:
                    for action in code_actions:
                        kind = action.get('kind')
                        if kinds_include_kind([CodeActionKind.Refactor], kind):
                            self.refactor_actions_cache.append((sb.session.config.name, action))
                        elif kinds_include_kind([CodeActionKind.Source], kind):
                            self.source_actions_cache.append((sb.session.config.name, action))
                return [action for action in code_actions if kinds_include_kind(only_kinds, action.get('kind'))]
            if manual:
                return [a for a in actions if not a.get('disabled')]
            # On implicit (selection change) request, only return commands and quick fix kinds.
            return [
                a for a in actions
                if is_command(a) or not a.get('disabled') and
                kinds_include_kind([CodeActionKind.QuickFix], a.get('kind', CodeActionKind.QuickFix))
            ]

        task = self._collect_code_actions_async(listener, request_factory, response_filter)
        if location_cache_key:
            self._response_cache = (location_cache_key, task)
        return task

    def request_on_save_async(
        self, view: sublime.View, on_save_actions: Dict[str, bool]
    ) -> Promise[List[CodeActionsByConfigName]]:
        listener = windows.listener_for_view(view)
        if not listener:
            return Promise.resolve([])
        region = entire_content_region(view)
        session_buffer_diagnostics, _ = listener.diagnostics_intersecting_region_async(region)

        def request_factory(sb: SessionBufferProtocol) -> Optional[Request]:
            session_kinds = get_session_kinds(sb)
            matching_kinds = get_matching_on_save_kinds(on_save_actions, session_kinds)
            if not matching_kinds:
                return None
            diagnostics = []  # type: List[Diagnostic]
            for sb, diags in session_buffer_diagnostics:
                if sb == sb:
                    diagnostics = diags
                    break
            params = text_document_code_action_params(view, region, diagnostics, matching_kinds, manual=False)
            return Request.codeAction(params, view)

        def response_filter(sb: SessionBufferProtocol, actions: List[CodeActionOrCommand]) -> List[CodeActionOrCommand]:
            # Filter actions returned from the session so that only matching kinds are collected.
            # Since older servers don't support the "context.only" property, those will return all
            # actions that need to be then manually filtered.
            session_kinds = get_session_kinds(sb)
            matching_kinds = get_matching_on_save_kinds(on_save_actions, session_kinds)
            return [a for a in actions if a.get('kind') in matching_kinds and not a.get('disabled')]

        return self._collect_code_actions_async(listener, request_factory, response_filter)

    def _collect_code_actions_async(
        self,
        listener: AbstractViewListener,
        request_factory: Callable[[SessionBufferProtocol], Optional[Request]],
        response_filter: Optional[Callable[[SessionBufferProtocol, List[CodeActionOrCommand]], List[CodeActionOrCommand]]] = None,  # noqa: E501
    ) -> Promise[List[CodeActionsByConfigName]]:

        def on_response(
            sb: SessionBufferProtocol, response: Union[Error, Optional[List[CodeActionOrCommand]]]
        ) -> CodeActionsByConfigName:
            actions = []
            if response and not isinstance(response, Error) and response_filter:
                actions = response_filter(sb, response)
            return (sb.session.config.name, actions)

        tasks = []  # type: List[Promise[CodeActionsByConfigName]]
        for sb in listener.session_buffers_async('codeActionProvider'):
            session = sb.session
            request = request_factory(sb)
            if request:
                response_handler = partial(on_response, sb)
                task = session.send_request_task(request)  # type: Promise[Optional[List[CodeActionOrCommand]]]
                tasks.append(task.then(response_handler))
        # Return only results for non-empty lists.
        return Promise.all(tasks) \
            .then(lambda actions_list: list(filter(lambda actions: len(actions[1]), actions_list)))


actions_manager = CodeActionsManager()


def get_session_kinds(sb: SessionBufferProtocol) -> List[CodeActionKind]:
    session_kinds = sb.get_capability('codeActionProvider.codeActionKinds')  # type: Optional[List[CodeActionKind]]
    return session_kinds or []


def get_matching_on_save_kinds(
    user_actions: Dict[str, bool], session_kinds: List[CodeActionKind]
) -> List[CodeActionKind]:
    """
    Filters user-enabled or disabled actions so that only ones matching the session kinds
    are returned. Returned kinds are those that are enabled and are not overridden by more
    specific, disabled kinds.

    Filtering only returns kinds that exactly match the ones supported by given session.
    If user has enabled a generic action that matches more specific session action
    (for example user's a.b matching session's a.b.c), then the more specific (a.b.c) must be
    returned as servers must receive only kinds that they advertise support for.
    """
    matching_kinds = []
    for session_kind in session_kinds:
        enabled = False
        action_parts = session_kind.split('.')
        for i in range(len(action_parts)):
            current_part = '.'.join(action_parts[0:i + 1])
            user_value = user_actions.get(current_part, None)
            if isinstance(user_value, bool):
                enabled = user_value
        if enabled:
            matching_kinds.append(session_kind)
    return matching_kinds


def kinds_include_kind(kinds: List[CodeActionKind], kind: Optional[CodeActionKind]) -> bool:
    """
    The "kinds" include "kind" if "kind" matches one of the "kinds" exactly or one of the "kinds" is a prefix
    of the whole "kind" (where prefix must be followed by a dot).
    """
    if not kind:
        return False
    for kinds_item in kinds:
        if kinds_item == kind:
            return True
        kinds_item_len = len(kinds_item)
        if len(kind) > kinds_item_len and kind.startswith(kinds_item) and kind[kinds_item_len] == '.':
            return True
    return False


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
        view_code_actions = cast(Dict[str, bool], view.settings().get('lsp_code_actions_on_save') or {})
        code_actions = userprefs().lsp_code_actions_on_save.copy()
        code_actions.update(view_code_actions)
        allowed_code_actions = dict()
        for key, value in code_actions.items():
            if key.startswith('source.'):
                allowed_code_actions[key] = value
        return allowed_code_actions

    def run_async(self) -> None:
        super().run_async()
        self._request_code_actions_async()

    def _request_code_actions_async(self) -> None:
        self._purge_changes_async()
        on_save_actions = self._get_code_actions_on_save(self._task_runner.view)
        actions_manager.request_on_save_async(self._task_runner.view, on_save_actions).then(self._handle_response_async)

    def _handle_response_async(self, responses: List[CodeActionsByConfigName]) -> None:
        if self._cancelled:
            return
        document_version = self._task_runner.view.change_count()
        tasks = []  # type: List[Promise]
        for config_name, code_actions in responses:
            session = self._task_runner.session_by_name(config_name, 'codeActionProvider')
            if session:
                tasks.extend([session.run_code_action_async(action, progress=False) for action in code_actions])
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

    def is_visible(
        self,
        event: Optional[dict] = None,
        point: Optional[int] = None,
        only_kinds: Optional[List[CodeActionKind]] = None
    ) -> bool:
        if self.applies_to_context_menu(event):
            return self.is_enabled(event, point)
        return True

    def run(
        self,
        edit: sublime.Edit,
        event: Optional[dict] = None,
        only_kinds: Optional[List[CodeActionKind]] = None,
        code_actions_by_config: Optional[List[CodeActionsByConfigName]] = None
    ) -> None:
        if code_actions_by_config:
            self._handle_code_actions(code_actions_by_config, run_first=True)
            return
        self._run_async(only_kinds)

    def _run_async(self, only_kinds: Optional[List[CodeActionKind]] = None) -> None:
        view = self.view
        region = first_selection_region(view)
        if region is None:
            return
        listener = windows.listener_for_view(view)
        if not listener:
            return
        session_buffer_diagnostics, covering = listener.diagnostics_intersecting_async(region)
        actions_manager \
            .request_for_region_async(view, covering, session_buffer_diagnostics, only_kinds, manual=True) \
            .then(lambda actions: sublime.set_timeout(lambda: self._handle_code_actions(actions)))

    def _handle_code_actions(self, response: List[CodeActionsByConfigName], run_first: bool = False) -> None:
        # Flatten response to a list of (config_name, code_action) tuples.
        actions = []  # type: List[Tuple[ConfigName, CodeActionOrCommand]]
        for config_name, session_actions in response:
            actions.extend([(config_name, action) for action in session_actions])
        if actions:
            if len(actions) == 1 and run_first:
                self._handle_select(0, actions)
            else:
                self._show_code_actions(actions)
        else:
            window = self.view.window()
            if window:
                window.status_message("No code actions available")

    def _show_code_actions(self, actions: List[Tuple[ConfigName, CodeActionOrCommand]]) -> None:
        window = self.view.window()
        if not window:
            return
        items, selected_index = format_code_actions_for_quick_panel(actions)
        window.show_quick_panel(
            items,
            lambda i: self._handle_select(i, actions),
            selected_index=selected_index,
            placeholder="Code action")

    def _handle_select(self, index: int, actions: List[Tuple[ConfigName, CodeActionOrCommand]]) -> None:
        if index == -1:
            return

        def run_async() -> None:
            config_name, action = actions[index]
            session = self.session_by_name(config_name)
            if session:
                session.run_code_action_async(action, progress=True) \
                    .then(lambda response: self._handle_response_async(config_name, response))

        sublime.set_timeout_async(run_async)

    def _handle_response_async(self, session_name: str, response: Any) -> None:
        if isinstance(response, Error):
            sublime.error_message("{}: {}".format(session_name, str(response)))


# This command must be a WindowCommand in order to reliably hide corresponding menu entries when no view has focus.
class LspMenuActionCommand(LspWindowCommand, metaclass=ABCMeta):
    """Handles a particular kind of code actions with the purpose to list them as items in a submenu."""

    capability = 'codeActionProvider'

    @property
    @abstractmethod
    def actions_cache(self) -> List[Tuple[str, CodeAction]]:
        ...

    @property
    def view(self) -> Optional[sublime.View]:
        return self.window.active_view()

    def is_enabled(self, id: int, event: Optional[dict] = None) -> bool:
        if not -1 < id < len(self.actions_cache):
            return False
        return self._has_session(event)

    def is_visible(self, id: int, event: Optional[dict] = None) -> bool:
        if id == -1:
            if self._has_session(event):
                sublime.set_timeout_async(partial(self._request_menu_actions_async, event))
            return False
        return id < len(self.actions_cache) and self._is_cache_valid(event)

    def _has_session(self, event: Optional[dict] = None) -> bool:
        view = self.view
        if not view:
            return False
        region = self._get_region(event)
        if region is None:
            return False
        listener = windows.listener_for_view(view)
        if not listener:
            return False
        return bool(listener.session_async(self.capability, region.b))

    def description(self, id: int, event: Optional[dict] = None) -> Optional[str]:
        if -1 < id < len(self.actions_cache):
            return self.actions_cache[id][1]['title']

    def want_event(self) -> bool:
        return True

    def run(self, id: int, event: Optional[dict] = None) -> None:
        sublime.set_timeout_async(partial(self.run_async, id, event))

    def run_async(self, id: int, event: Optional[dict]) -> None:
        if self._is_cache_valid(event):
            config_name, action = self.actions_cache[id]
            session = self.session_by_name(config_name)
            if session:
                session.run_code_action_async(action, progress=True) \
                    .then(lambda response: self._handle_response_async(config_name, response))

    def _handle_response_async(self, session_name: str, response: Any) -> None:
        if isinstance(response, Error):
            sublime.error_message("{}: {}".format(session_name, str(response)))

    def _is_cache_valid(self, event: Optional[dict]) -> bool:
        view = self.view
        if not view:
            return False
        region = self._get_region(event)
        if region is None:
            return False
        return actions_manager.menu_actions_cache_key == "{}#{}:{}".format(
            view.buffer_id(), view.change_count(), region)

    def _get_region(self, event: Optional[dict]) -> Optional[sublime.Region]:
        view = self.view
        if not view:
            return None
        if event is not None and self.applies_to_context_menu(event):
            return sublime.Region(view.window_to_text((event['x'], event['y'])))
        return first_selection_region(view)

    @staticmethod
    def applies_to_context_menu(event: Optional[dict]) -> bool:
        return event is not None and 'x' in event

    def _request_menu_actions_async(self, event: Optional[dict]) -> None:
        view = self.view
        if not view:
            return
        region = self._get_region(event)
        if region is not None:
            actions_manager.request_for_region_async(view, region, [], MENU_ACTIONS_KINDS, True)


class LspRefactorCommand(LspMenuActionCommand):

    @property
    def actions_cache(self) -> List[Tuple[str, CodeAction]]:
        return actions_manager.refactor_actions_cache


class LspSourceActionCommand(LspMenuActionCommand):

    @property
    def actions_cache(self) -> List[Tuple[str, CodeAction]]:
        return actions_manager.source_actions_cache
