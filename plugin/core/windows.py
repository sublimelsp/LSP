from ...third_party import WebsocketServer  # type: ignore
from .configurations import ConfigManager
from .configurations import WindowConfigManager
from .diagnostics import DiagnosticsStorage
from .logging import debug
from .logging import exception_log
from .message_request_handler import MessageRequestHandler
from .protocol import Error
from .protocol import Notification, TextDocumentSyncKindNone, TextDocumentSyncKindFull
from .rpc import Logger
from .sessions import get_plugin
from .sessions import Manager
from .sessions import Session
from .settings import settings
from .transports import create_transport
from .types import ClientConfig
from .types import ClientStates
from .types import Settings
from .types import view2scope
from .types import ViewLike
from .types import WindowLike
from .typing import Optional, List, Callable, Dict, Any, Protocol, Set, Iterable, Generator
from .views import did_change, did_close, did_open, did_save, will_save
from .views import extract_variables
from .workspace import disable_in_project
from .workspace import enable_in_project
from .workspace import ProjectFolders
from .workspace import sorted_workspace_folders
from copy import deepcopy
from time import time
from weakref import ref
from weakref import WeakValueDictionary
import json
import sublime
import threading


def debounced(f: Callable[[], None], timeout_ms: int = 0, condition: Callable[[], bool] = lambda: True,
              async_thread: bool = False) -> None:
    """
    Possibly run a function at a later point in time, either on the async thread or on the main thread.

    :param      f:             The function to possibly run
    :param      timeout_ms:    The time in milliseconds after which to possibly to run the function
    :param      condition:     The condition that must evaluate to True in order to run the funtion
    :param      async_thread:  If true, run the function on the async worker thread, otherwise run the function on the
                               main thread
    """

    def run() -> None:
        if condition():
            f()

    runner = sublime.set_timeout_async if async_thread else sublime.set_timeout
    runner(run, timeout_ms)


class SublimeLike(Protocol):

    def set_timeout_async(self, f: Callable, timeout_ms: int = 0) -> None:
        ...

    def Region(self, a: int, b: int) -> 'Any':
        ...


class DocumentHandler(Protocol):
    def add_session(self, session: Session) -> None:
        ...

    def remove_session(self, config_name: str) -> None:
        ...

    def reset(self) -> None:
        ...

    def handle_did_open(self, view: ViewLike) -> None:
        ...

    def handle_did_change(self, view: ViewLike, changes: Iterable[sublime.TextChange]) -> None:
        ...

    def notify_sessions(self, view: ViewLike, buffer_changes: Optional[List[sublime.TextChange]]) -> None:
        ...

    def purge_changes(self, view: ViewLike) -> None:
        ...

    def handle_will_save(self, view: ViewLike, reason: int) -> None:
        ...

    def handle_did_save(self, view: ViewLike) -> None:
        ...

    def handle_did_close(self, view: ViewLike) -> None:
        ...

    def has_document_state(self, file_name: str) -> bool:
        ...


def get_active_views(window: WindowLike) -> List[ViewLike]:
    views = list()  # type: List[ViewLike]
    num_groups = window.num_groups()
    for group in range(0, num_groups):
        view = window.active_view_in_group(group)
        debug("group {} view {}".format(group, view.file_name()))
        if window.active_group() == group:
            views.insert(0, view)
        else:
            views.append(view)

    return views


class DocumentHandlerFactory(object):
    def __init__(self, sublime: Any, settings: Settings) -> None:
        self._sublime = sublime
        self._settings = settings

    def for_window(self, window: WindowLike, workspace: ProjectFolders,
                   configs: WindowConfigManager) -> DocumentHandler:
        return WindowDocumentHandler(self._sublime, self._settings, window, workspace, configs)


def nop() -> None:
    pass


class PendingBuffer:

    __slots__ = ('view', 'version', 'changes')

    def __init__(self, view: ViewLike, version: int, changes: Iterable[sublime.TextChange]) -> None:
        self.view = view
        self.version = version
        self.changes = list(changes)

    def update(self, version: int, changes: Iterable[sublime.TextChange]) -> None:
        self.version = version
        self.changes.extend(changes)


class WindowDocumentHandler(object):
    def __init__(self, sublime: Any, settings: Settings, window: WindowLike, workspace: ProjectFolders,
                 configs: WindowConfigManager) -> None:
        self._sublime = sublime
        self._settings = settings
        self._configs = configs
        self._window = window
        self._document_states = set()  # type: Set[str]
        self._pending_buffer_changes = dict()  # type: Dict[int, PendingBuffer]
        self._sessions = dict()  # type: Dict[str, List[Session]]
        self._workspace = workspace
        self.changed = nop
        self.saved = nop

    def add_session(self, session: Session) -> None:
        self._sessions.setdefault(session.config.name, []).append(session)
        self._notify_open_documents(session)

    def remove_session(self, config_name: str) -> None:
        if config_name in self._sessions:
            del self._sessions[config_name]

    def reset(self) -> None:
        for view in self._window.views():
            self.detach_view(view)
        self._document_states.clear()

    def has_document_state(self, path: str) -> bool:
        return path in self._document_states

    def _get_applicable_sessions(self, view: ViewLike) -> List[Session]:
        sessions = []  # type: List[Session]
        # ViewLike vs sublime.View
        scope = view2scope(view)  # type: ignore

        for config_name, config_sessions in self._sessions.items():
            for session in config_sessions:
                if session.config.match_document(scope) and session.handles_path(view.file_name()):
                    sessions.append(session)

        return sessions

    def _notify_open_documents(self, session: Session) -> None:
        # Note: a copy is made of self._document_states because it may be modified in another thread.
        for file_name in list(self._document_states):
            if session.handles_path(file_name):
                view = self._window.find_open_file(file_name)
                if view:
                    # ViewLike vs sublime.View
                    if session.config.match_document(view2scope(view)):  # type: ignore
                        sessions = self._get_applicable_sessions(view)
                        self._attach_view(view, sessions)
                        for session in sessions:
                            if session.should_notify_did_open():
                                self._notify_did_open(view, session)

    def _attach_view(self, view: ViewLike, sessions: List[Session]) -> None:
        view.settings().set("show_definitions", False)
        if self._settings.show_view_status:
            view.set_status("lsp_clients", ", ".join(session.config.name for session in sessions))

    def detach_view(self, view: ViewLike) -> None:
        view.settings().erase("show_definitions")
        view.set_status("lsp_clients", "")

    def _view_language(self, view: ViewLike, config_name: str) -> str:
        return view.settings().get('lsp_language')[config_name]

    def _set_view_languages(self, view: ViewLike, configurations: Iterable[ClientConfig]) -> None:
        # HACK! languageId <--> view base scope should be UNIQUE
        languages = {}
        base_scope = view2scope(view)  # type: ignore
        for config in configurations:
            for language in config.languages:
                if language.match_document(base_scope):
                    # bad :( all values should be exactly the same language.id
                    languages[config.name] = language.id
                    break
        view.settings().set('lsp_language', languages)  # TODO: this should be a single languageId
        view.settings().set('lsp_active', True)

    def handle_did_open(self, view: ViewLike) -> None:
        file_name = view.file_name()
        if file_name and file_name not in self._document_states:
            configurations = list(self._configs.match_view(view))  # type: ignore
            if len(configurations) > 0:
                # always register a supported document
                self._document_states.add(file_name)
                self._set_view_languages(view, configurations)

                # the sessions may not be available yet,
                # the document will get synced when a session is added.
                sessions = self._get_applicable_sessions(view)
                self._attach_view(view, sessions)
                for session in sessions:
                    if session.should_notify_did_open():
                        self._notify_did_open(view, session)

    def _notify_did_open(self, view: ViewLike, session: Session) -> None:
        language_id = self._view_language(view, session.config.name)
        # There might be pending, no longer valid changes when restoring session.
        self._pending_buffer_changes.pop(view.buffer_id(), None)
        # mypy: expected sublime.View, got ViewLike
        session.send_notification(did_open(view, language_id))  # type: ignore

    def handle_did_close(self, view: ViewLike) -> None:
        file_name = view.file_name() or ""
        try:
            self._document_states.remove(file_name)
        except KeyError:
            return
        # mypy: expected sublime.View, got ViewLike
        notification = did_close(view)  # type: ignore
        for session in self._get_applicable_sessions(view):
            if session.should_notify_did_close():
                session.send_notification(notification)

    def handle_will_save(self, view: ViewLike, reason: int) -> None:
        file_name = view.file_name()
        if file_name in self._document_states:
            for session in self._get_applicable_sessions(view):
                if session.should_notify_will_save():
                    # mypy: expected sublime.View, got ViewLike
                    session.send_notification(will_save(view, reason))  # type: ignore

    def handle_did_save(self, view: ViewLike) -> None:
        file_name = view.file_name()
        if file_name in self._document_states:
            self.purge_changes(view)
            for session in self._get_applicable_sessions(view):
                if session:
                    send_did_save, include_text = session.should_notify_did_save()
                    if send_did_save:
                        # mypy: expected sublime.View, got ViewLike
                        session.send_notification(did_save(view, include_text))  # type: ignore
            self.saved()
        else:
            debug('document not tracked', file_name)

    def handle_did_change(self, view: ViewLike, changes: Iterable[sublime.TextChange]) -> None:
        buffer_id = view.buffer_id()
        change_count = view.change_count()
        pending_buffer = self._pending_buffer_changes.get(buffer_id)
        if pending_buffer is None:
            self._pending_buffer_changes[buffer_id] = PendingBuffer(view, change_count, changes)
        else:
            pending_buffer.update(change_count, changes)
        debounced(lambda: self.purge_did_change(buffer_id, change_count), 500,
                  lambda: view.change_count() == change_count, async_thread=True)

    def purge_changes(self, view: ViewLike) -> None:
        self.purge_did_change(view.buffer_id())

    def purge_did_change(self, buffer_id: int, buffer_version: Optional[int] = None) -> None:
        pending_buffer = self._pending_buffer_changes.get(buffer_id, None)
        if pending_buffer is not None:
            if buffer_version is None or buffer_version == pending_buffer.version:
                self._pending_buffer_changes.pop(buffer_id, None)
                self.notify_did_change(pending_buffer)
                self.changed()

    def notify_did_change(self, pending_buffer: PendingBuffer) -> None:
        view = pending_buffer.view
        if not view.is_valid():
            return
        file_name = view.file_name()
        if not file_name or view.window() != self._window:
            return
        # ensure view is opened.
        if file_name not in self._document_states:
            self.handle_did_open(view)
        self.notify_sessions(view, pending_buffer.changes)

    def notify_sessions(self, view: ViewLike, buffer_changes: Optional[List[sublime.TextChange]]) -> None:
        for session in self._get_applicable_sessions(view):
            if session.state != ClientStates.READY:
                continue
            sync_kind = session.text_sync_kind()
            if sync_kind == TextDocumentSyncKindNone:
                continue
            changes = None if sync_kind == TextDocumentSyncKindFull else buffer_changes
            # ViewLike vs sublime.View
            notification = did_change(view, changes)  # type: ignore
            session.send_notification(notification)


def extract_message(params: Any) -> str:
    return params.get("message", "???") if isinstance(params, dict) else "???"


class WindowManager(Manager):
    def __init__(
        self,
        window: WindowLike,
        workspace: ProjectFolders,
        settings: Settings,
        configs: WindowConfigManager,
        documents: DocumentHandler,
        diagnostics: DiagnosticsStorage,
        sublime: Any,
        server_panel_factory: Optional[Callable] = None
    ) -> None:
        self._window = window
        self._settings = settings
        self._configs = configs
        self.diagnostics = diagnostics
        self.documents = documents
        self.server_panel_factory = server_panel_factory
        self._sessions = dict()  # type: Dict[str, List[Session]]
        self._next_initialize_views = list()  # type: List[ViewLike]
        self._sublime = sublime
        self._restarting = False
        self._is_closing = False
        self._initialization_lock = threading.Lock()
        self._workspace = workspace

    def on_load_project(self) -> None:
        # TODO: Also end sessions that were previously enabled in the .sublime-project, but now disabled or removed
        # from the .sublime-project.
        self._configs.update()
        workspace_folders = self._workspace.update()
        for sessions in self._sessions.values():
            for session in sessions:
                session.update_folders(workspace_folders)

    def on_pre_close_project(self) -> None:
        self.end_sessions()

    def window(self) -> sublime.Window:
        # WindowLike vs. sublime
        return self._window  # type: ignore

    def sessions(self, view: sublime.View, capability: Optional[str] = None) -> Generator[Session, None, None]:
        for sessions in self._sessions.values():
            for session in sessions:
                if session.can_handle(view, capability):
                    yield session

    def get_session(self, config_name: str, file_path: str) -> Optional[Session]:
        return self._find_session(config_name, file_path)

    def _is_session_ready(self, config_name: str, file_path: str) -> bool:
        maybe_session = self._find_session(config_name, file_path)
        return maybe_session is not None and maybe_session.state == ClientStates.READY

    def _can_start_config(self, config_name: str, file_path: str) -> bool:
        return not bool(self._find_session(config_name, file_path))

    def _find_session(self, config_name: str, file_path: str) -> Optional[Session]:
        if config_name in self._sessions:
            for session in self._sessions[config_name]:
                if session.handles_path(file_path):
                    return session
        return None

    def enable_config(self, config_name: str) -> None:
        enable_in_project(self._window, config_name)
        self._configs.update()
        self._sublime.set_timeout_async(self.start_active_views, 500)
        self._window.status_message("{} enabled, starting server...".format(config_name))

    def disable_config(self, config_name: str) -> None:
        disable_in_project(self._window, config_name)
        self._configs.update()
        self.end_config_sessions(config_name)

    def start_active_views(self) -> None:
        active_views = get_active_views(self._window)
        debug('window {} starting {} initial views'.format(self._window.id(), len(active_views)))
        for view in active_views:
            if view.file_name():
                self._workspace.update()
                self._initialize_on_open(view)
                self.documents.handle_did_open(view)

    def activate_view(self, view: ViewLike) -> None:
        file_name = view.file_name() or ""
        if not self.documents.has_document_state(file_name):
            self._workspace.update()
            self._initialize_on_open(view)

    def _open_after_initialize(self, view: ViewLike) -> None:
        if any(v for v in self._next_initialize_views if v.id() == view.id()):
            return
        self._next_initialize_views.append(view)

    def _open_pending_views(self) -> None:
        opening = list(self._next_initialize_views)
        self._next_initialize_views = []
        for view in opening:
            debug('opening after initialize', view.file_name())
            self._initialize_on_open(view)

    def _initialize_on_open(self, view: ViewLike) -> None:
        file_path = view.file_name() or ""

        if not self._workspace.includes_path(file_path):
            return

        def needed_configs(configs: Iterable[ClientConfig]) -> List[ClientConfig]:
            new_configs = []
            for c in configs:
                if c.name not in self._sessions:
                    new_configs.append(c)
                else:
                    session = next((s for s in self._sessions[c.name] if s.handles_path(file_path)), None)
                    if session:
                        if session.state != ClientStates.READY:
                            debug('scheduling for delayed open, session {} not ready: {}'.format(c.name, file_path))
                            self._open_after_initialize(view)
                        else:
                            debug('found ready session {} for {}'.format(c.name, file_path))
                    else:
                        debug('path not in existing {} session: {}'.format(c.name, file_path))
                        new_configs.append(c)

            return new_configs

        # have all sessions for this document been started?
        with self._initialization_lock:
            # ViewLike vs sublime.View
            startable_configs = needed_configs(self._configs.match_view(view))  # type: ignore
            for config in startable_configs:
                debug("window {} requests {} for {}".format(self._window.id(), config.name, file_path))
                self.start(config, view)  # type: ignore

    def start(self, config: ClientConfig, initiating_view: sublime.View) -> None:
        file_path = initiating_view.file_name() or ''
        if not self._can_start_config(config.name, file_path):
            debug('Already starting on this window:', config.name)
            return
        try:
            workspace_folders = sorted_workspace_folders(self._workspace.folders, file_path)
            plugin_class = get_plugin(config.name)
            if plugin_class is not None:
                if plugin_class.needs_update_or_installation():
                    self._window.status_message('Installing {} ...'.format(config.name))
                    plugin_class.install_or_update()
                # WindowLike vs. sublime.Window
                cannot_start_reason = plugin_class.can_start(
                    self._window, initiating_view, workspace_folders, config)  # type: ignore
                if cannot_start_reason:
                    self._window.status_message(cannot_start_reason)
                    return
            session = Session(self, self._create_loggers(config.name), workspace_folders, config, plugin_class)
            cwd = workspace_folders[0].path if workspace_folders else None
            variables = extract_variables(self._window)  # type: ignore
            if plugin_class is not None:
                additional_variables = plugin_class.additional_variables()
                if isinstance(additional_variables, dict):
                    variables.update(additional_variables)
            # WindowLike vs sublime.Window
            self._window.status_message("Starting {} ...".format(config.name))
            transport = create_transport(config, cwd, self._window, session, variables)  # type: ignore
            self._window.status_message("Initializing {} ...".format(config.name))
            session.initialize(variables, transport)
            self._sessions.setdefault(config.name, []).append(session)
            debug("window {} added session {}".format(self._window.id(), config.name))
        except Exception as e:
            message = "\n\n".join([
                "Could not start {}",
                "{}",
                "Server will be disabled for this window"
            ]).format(config.name, str(e))
            exception_log("Unable to start {}".format(config.name), e)
            self._configs.disable_temporarily(config.name)
            self._sublime.message_dialog(message)

    def _create_loggers(self, config_name: str) -> List[Logger]:
        logger_map = {
            "panel": PanelLogger,
            "websocket": RemoteLogger,
        }
        loggers = []
        for logger_type in settings.log_server:
            if logger_type not in logger_map:
                debug("Invalid logger type ({}) specified for log_server settings".format(logger_type))
                continue
            loggers.append(logger_map[logger_type](self, config_name))
        return loggers

    def handle_message_request(self, session: Session, params: Any, request_id: Any) -> None:
        handler = MessageRequestHandler(self._window.active_view(), session, request_id, params,  # type: ignore
                                        session.config.name)
        handler.show()

    def restart_sessions(self) -> None:
        self._restarting = True
        self.end_sessions()

    def end_sessions(self) -> None:
        self.documents.reset()
        for config_name in list(self._sessions):
            self.end_config_sessions(config_name)

    def end_config_sessions(self, config_name: str) -> None:
        config_sessions = self._sessions.pop(config_name, [])
        for session in config_sessions:
            session.end()

    def get_project_path(self, file_path: str) -> Optional[str]:
        candidate = None  # type: Optional[str]
        for folder in self._workspace.folders:
            if file_path.startswith(folder):
                if candidate is None or len(folder) > len(candidate):
                    candidate = folder
        return candidate

    def on_post_initialize(self, session: Session) -> None:
        with self._initialization_lock:
            session.send_notification(Notification.initialized())
            document_sync = session.capabilities.get("textDocumentSync")
            if document_sync:
                self.documents.add_session(session)
            self._window.status_message("{} initialized".format(session.config.name))
            sublime.set_timeout_async(self._open_pending_views)

    def handle_view_closed(self, view: ViewLike) -> None:
        if view.file_name():
            if not self._is_closing:
                if not self._window.is_valid():
                    # try to detect close synchronously (for quitting)
                    self._handle_window_closed()
                else:
                    # in case the window is invalidated after the last view is closed
                    self._sublime.set_timeout_async(lambda: self._check_window_closed(), 100)

    def _check_window_closed(self) -> None:
        if not self._is_closing and not self._window.is_valid():
            self._handle_window_closed()

    def _handle_window_closed(self) -> None:
        debug('window {} closed, ending sessions'.format(self._window.id()))
        self._is_closing = True
        self.end_sessions()

    def _handle_all_sessions_ended(self) -> None:
        debug('clients for window {} unloaded'.format(self._window.id()))
        if self._restarting:
            debug('window {} sessions unloaded - restarting'.format(self._window.id()))
            sublime.set_timeout(self.start_active_views, 0)

    def on_post_exit(self, session: Session, exit_code: int, exception: Optional[Exception]) -> None:
        sublime.set_timeout(lambda: self._on_post_exit_main_thread(session, exit_code, exception))

    def _on_post_exit_main_thread(self, session: Session, exit_code: int, exception: Optional[Exception]) -> None:
        self.documents.remove_session(session.config.name)
        for view in self._window.views():
            file_name = view.file_name()
            if file_name:
                self.diagnostics.remove(file_name, session.config.name)
        sessions = self._sessions.get(session.config.name)
        if sessions is not None:
            sessions = [s for s in sessions if id(s) != id(session)]
            if sessions:
                self._sessions[session.config.name] = sessions
            else:
                self._sessions.pop(session.config.name)
        if exit_code != 0:
            self._window.status_message("{} exited with status code {}".format(session.config.name, exit_code))
            fmt = "{0} exited with status code {1}.\n\nDo you want to restart {0}?\n\nIf you choose Cancel, {0} will "\
                  "be disabled for this window until you restart Sublime Text."
            msg = fmt.format(session.config.name, exit_code)
            if sublime.ok_cancel_dialog(msg, "Restart {}".format(session.config.name)):
                v = self._window.active_view()
                if not v:
                    return
                sublime.set_timeout(lambda: self.start(session.config, v))  # type: ignore
            else:
                self._configs.disable_temporarily(session.config.name)
        if exception:
            self._window.status_message("{} exited with an exception: {}".format(session.config.name, exception))
        if not self._sessions:
            self._handle_all_sessions_ended()

    def handle_server_message(self, server_name: str, message: str) -> None:
        if not self.server_panel_factory:
            return
        panel = self.server_panel_factory(self._window)
        if not panel:
            return debug("no server panel for window", self._window.id())
        panel.run_command("lsp_update_server_panel", {"prefix": server_name, "message": message})

    def handle_log_message(self, session: Session, params: Any) -> None:
        self.handle_server_message(session.config.name, extract_message(params))

    def handle_stderr_log(self, session: Session, message: str) -> None:
        if self._settings.log_stderr:
            self.handle_server_message(session.config.name, message)

    def handle_show_message(self, session: Session, params: Any) -> None:
        self._sublime.status_message("{}: {}".format(session.config.name, extract_message(params)))


class WindowRegistry(object):
    def __init__(self, configs: ConfigManager, documents: Any, sublime: Any) -> None:
        self._windows = WeakValueDictionary()  # type: WeakValueDictionary[int, WindowManager]
        self._configs = configs
        self._documents = documents
        self._sublime = sublime
        self._diagnostics_ui_class = None  # type: Optional[Callable]
        self._server_panel_factory = None  # type: Optional[Callable]
        self._settings = None  # type: Optional[Settings]

    def set_diagnostics_ui(self, ui_class: Any) -> None:
        self._diagnostics_ui_class = ui_class

    def set_server_panel_factory(self, factory: Callable) -> None:
        self._server_panel_factory = factory

    def set_settings_factory(self, settings: Settings) -> None:
        self._settings = settings

    def lookup(self, window: Any) -> WindowManager:
        state = self._windows.get(window.id())
        if state is None:
            if not self._settings:
                raise RuntimeError("no settings")
            workspace = ProjectFolders(window)
            window_configs = self._configs.for_window(window)
            window_documents = self._documents.for_window(window, workspace, window_configs)
            diagnostics_ui = self._diagnostics_ui_class(window,
                                                        window_documents) if self._diagnostics_ui_class else None
            state = WindowManager(
                window=window,
                workspace=workspace,
                settings=self._settings,
                configs=window_configs,
                documents=window_documents,
                diagnostics=DiagnosticsStorage(diagnostics_ui),
                sublime=self._sublime,
                server_panel_factory=self._server_panel_factory)
            self._windows[window.id()] = state
        return state


class PanelLogger(Logger):

    def __init__(self, manager: WindowManager, server_name: str) -> None:
        self._manager = ref(manager)
        self._server_name = server_name

    def log(self, message: str, params: Any, log_payload: bool = True) -> None:

        def run_on_async_worker_thread() -> None:
            nonlocal message
            if log_payload:
                message = "{}: {}".format(message, params)
            manager = self._manager()
            if manager is not None:
                manager.handle_server_message(":", message)

        sublime.set_timeout_async(run_on_async_worker_thread)

    def outgoing_response(self, request_id: Any, params: Any) -> None:
        if not settings.log_server:
            return
        self.log(self._format_response(">>>", request_id), params)

    def outgoing_error_response(self, request_id: Any, error: Error) -> None:
        if not settings.log_server:
            return
        self.log(self._format_response("~~>", request_id), error.to_lsp())

    def outgoing_request(self, request_id: int, method: str, params: Any, blocking: bool) -> None:
        if not settings.log_server:
            return
        direction = "==>" if blocking else "-->"
        self.log(self._format_request(direction, method, request_id), params)

    def outgoing_notification(self, method: str, params: Any) -> None:
        if not settings.log_server:
            return
        # Do not log the payloads if any of these conditions occur because the payloads might contain the entire
        # content of the view.
        log_payload = True
        if method.endswith("didOpen"):
            log_payload = False
        elif method.endswith("didChange"):
            content_changes = params.get("contentChanges")
            if content_changes and "range" not in content_changes[0]:
                log_payload = False
        elif method.endswith("didSave"):
            if isinstance(params, dict) and "text" in params:
                log_payload = False
        self.log(self._format_notification(" ->", method), params, log_payload)

    def incoming_response(self, request_id: int, params: Any, is_error: bool, blocking: bool) -> None:
        if not settings.log_server:
            return
        if is_error:
            direction = "<~~"
        else:
            direction = "<==" if blocking else "<<<"
        self.log(self._format_response(direction, request_id), params)

    def incoming_request(self, request_id: Any, method: str, params: Any) -> None:
        if not settings.log_server:
            return
        self.log(self._format_request("<--", method, request_id), params)

    def incoming_notification(self, method: str, params: Any, unhandled: bool) -> None:
        if not settings.log_server or method == "window/logMessage":
            return
        direction = "<? " if unhandled else "<- "
        self.log(self._format_notification(direction, method), params)

    def _format_response(self, direction: str, request_id: Any) -> str:
        return "{} {} {}".format(direction, self._server_name, request_id)

    def _format_request(self, direction: str, method: str, request_id: Any) -> str:
        return "{} {} {}({})".format(direction, self._server_name, method, request_id)

    def _format_notification(self, direction: str, method: str) -> str:
        return "{} {} {}".format(direction, self._server_name, method)


class RemoteLogger(Logger):
    PORT = 9981
    DIRECTION_OUTGOING = 1
    DIRECTION_INCOMING = 2
    _ws_server = None  # type: Optional[WebsocketServer]
    _ws_server_thread = None  # type: Optional[threading.Thread]

    def __init__(self, manager: WindowManager, server_name: str) -> None:
        self._manager = ref(manager)
        self._server_name = server_name
        if not RemoteLogger._ws_server:
            try:
                RemoteLogger._ws_server = WebsocketServer(self.PORT)
                RemoteLogger._ws_server.set_fn_new_client(self._on_new_client)
                RemoteLogger._ws_server.set_fn_client_left(self._on_client_left)
                RemoteLogger._ws_server.set_fn_message_received(self._on_message_received)
            except OSError as ex:
                if ex.errno == 48:  # Address already in use
                    debug('WebsocketServer not started - address already in use')
                    RemoteLogger._ws_server = None
                else:
                    raise ex
        self._start_server()

    def _start_server(self) -> None:
        if RemoteLogger._ws_server:
            def start_async() -> None:
                if RemoteLogger._ws_server:
                    RemoteLogger._ws_server.run_forever()
            RemoteLogger._ws_server_thread = threading.Thread(target=start_async)
            RemoteLogger._ws_server_thread.start()

    def _stop_server(self) -> None:
        if RemoteLogger._ws_server:
            RemoteLogger._ws_server.shutdown()
            RemoteLogger._ws_server = None
            if RemoteLogger._ws_server_thread:
                RemoteLogger._ws_server_thread.join()
                RemoteLogger._ws_server_thread = None

    def _on_new_client(self, client: Dict, server: WebsocketServer) -> None:
        """Called for every client connecting (after handshake)."""
        debug("New client connected and was given id %d" % client['id'])
        # server.send_message_to_all("Hey all, a new client has joined us")

    def _on_client_left(self, client: Dict, server: WebsocketServer) -> None:
        """Called for every client disconnecting."""
        debug("Client(%d) disconnected" % client['id'])

    def _on_message_received(self, client: Dict, server: WebsocketServer, message: str) -> None:
        """Called when a client sends a message."""
        debug("Client(%d) said: %s" % (client['id'], message))

    def outgoing_request(self, request_id: int, method: str, params: Any, blocking: bool) -> None:
        self._broadcast_json({
            'server': self._server_name,
            'id': request_id,
            'time': round(time() * 1000),
            'method': method,
            'params': params,
            'direction': self.DIRECTION_OUTGOING,
            'blocking': blocking
        })

    def incoming_response(self, request_id: int, params: Any, is_error: bool, blocking: bool) -> None:
        self._broadcast_json({
            'server': self._server_name,
            'id': request_id,
            'time': round(time() * 1000),
            'params': params,
            'direction': self.DIRECTION_INCOMING,
            'isError': is_error,
            'blocking': blocking
        })

    def incoming_request(self, request_id: Any, method: str, params: Any) -> None:
        self._broadcast_json({
            'server': self._server_name,
            'id': request_id,
            'time': round(time() * 1000),
            'method': method,
            'params': params,
            'direction': self.DIRECTION_INCOMING,
        })

    def outgoing_response(self, request_id: Any, params: Any) -> None:
        self._broadcast_json({
            'server': self._server_name,
            'id': request_id,
            'time': round(time() * 1000),
            'params': params,
            'direction': self.DIRECTION_OUTGOING,
        })

    def outgoing_error_response(self, request_id: Any, error: Error) -> None:
        self._broadcast_json({
            'server': self._server_name,
            'id': request_id,
            'isError': True,
            'params': error.to_lsp(),
            'time': round(time() * 1000),
            'direction': self.DIRECTION_OUTGOING,
        })

    def outgoing_notification(self, method: str, params: Any) -> None:
        trimmed_params = deepcopy(params)
        if method.endswith("didOpen"):
            if isinstance(params, dict) and "textDocument" in params:
                trimmed_params['textDocument']['text'] = '[trimmed]'
        elif method.endswith("didChange"):
            content_changes = params.get("contentChanges")
            if content_changes and "range" not in content_changes[0]:
                pass
        elif method.endswith("didSave"):
            if isinstance(params, dict) and "text" in params:
                trimmed_params['text'] = '[trimmed]'
        self._broadcast_json({
            'server': self._server_name,
            'time': round(time() * 1000),
            'method': method,
            'params': trimmed_params,
            'direction': self.DIRECTION_OUTGOING,
        })

    def incoming_notification(self, method: str, params: Any, unhandled: bool) -> None:
        self._broadcast_json({
            'server': self._server_name,
            'time': round(time() * 1000),
            'error': 'Unhandled notification!' if unhandled else None,
            'method': method,
            'params': params,
            'direction': self.DIRECTION_INCOMING,
        })

    def _broadcast_json(self, data: Dict[str, Any]) -> None:
        if RemoteLogger._ws_server:
            json_data = json.dumps(data, sort_keys=True, check_circular=False, separators=(',', ':'))
            RemoteLogger._ws_server.send_message_to_all(json_data)
        else:
            debug('Failed to broadcast a remote log message')
