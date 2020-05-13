from .configurations import ConfigManager
from .configurations import WindowConfigManager
from .diagnostics import DiagnosticsStorage
from .logging import debug, exception_log
from .message_request_handler import MessageRequestHandler
from .protocol import Notification, TextDocumentSyncKindNone, TextDocumentSyncKindFull
from .sessions import Manager
from .sessions import Session
from .settings import client_configs
from .transports import create_transport
from .types import ClientConfig
from .types import ClientStates
from .types import Settings
from .types import view2scope
from .types import ViewLike
from .types import WindowLike
from .typing import Optional, List, Callable, Dict, Any, Protocol, Set, Iterable, Generator, Type
from .views import did_change, did_close, did_open, did_save, will_save
from .workspace import disable_in_project
from .workspace import enable_in_project
from .workspace import get_workspace_folders
from .workspace import ProjectFolders
from .workspace import sorted_workspace_folders
from weakref import ref
from weakref import WeakValueDictionary
import os
import sublime
import tempfile
import threading


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


_session_types = {}  # type: Dict[str, Type[Session]]


def register_session_type(session_type: Type[Session]) -> None:
    if issubclass(session_type, Session):
        try:
            name = session_type.name()
            if name not in _session_types:
                config = session_type.standard_configuration()
                _session_types[name] = session_type
                client_configs.add_external_config(config)
                client_configs.update_configs()
                debug("Registered", name)
        except Exception as ex:
            exception_log("Failed to register session type", ex)


def unregister_session_type(session_type: Type[Session]) -> None:
    name = session_type.name()
    try:
        _session_types.pop(name)
        client_configs.remove_external_config(name)
        debug("Unregistered", name)
    except KeyError:
        pass


def get_session_type(name: str) -> Type[Session]:
    global _session_types
    return _session_types.get(name, Session)


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
        self._sublime.set_timeout_async(lambda: self.purge_did_change(buffer_id, change_count), 500)

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
        for session in self._get_applicable_sessions(view):
            if session.state != ClientStates.READY:
                continue
            sync_kind = session.text_sync_kind()
            if sync_kind == TextDocumentSyncKindNone:
                continue
            changes = None if sync_kind == TextDocumentSyncKindFull else pending_buffer.changes
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
        weakself = ref(self)

        # A weak reference is needed, otherwise self._workspace will have a strong reference to self, meaning a
        # cyclic dependency.
        def on_changed(folders: List[str]) -> None:
            this = weakself()
            if this is not None:
                this._on_project_changed(folders)

        # A weak reference is needed, otherwise self._workspace will have a strong reference to self, meaning a
        # cyclic dependency.
        def on_switched(folders: List[str]) -> None:
            this = weakself()
            if this is not None:
                this._on_project_switched(folders)

        self._workspace.on_changed = on_changed
        self._workspace.on_switched = on_switched
        self._progress = dict()  # type: Dict[Any, Any]

    def window(self) -> sublime.Window:
        # WindowLike vs. sublime
        return self._window  # type: ignore

    def sessions(self, view: sublime.View, capability: Optional[str] = None) -> Generator[Session, None, None]:
        file_name = view.file_name() or ''
        for sessions in self._sessions.values():
            for session in sessions:
                if capability is None or capability in session.capabilities:
                    if session.state == ClientStates.READY and session.handles_path(file_name):
                        yield session

    def _on_project_changed(self, folders: List[str]) -> None:
        workspace_folders = get_workspace_folders(self._workspace.folders)
        for config_name in self._sessions:
            for session in self._sessions[config_name]:
                session.update_folders(workspace_folders)

    def _on_project_switched(self, folders: List[str]) -> None:
        debug('project switched - ending all sessions')
        self.end_sessions()

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

    def update_configs(self) -> None:
        self._configs.update()

    def enable_config(self, config_name: str) -> None:
        enable_in_project(self._window, config_name)
        self.update_configs()
        self._sublime.set_timeout_async(self.start_active_views, 500)
        self._window.status_message("{} enabled, starting server...".format(config_name))

    def disable_config(self, config_name: str) -> None:
        disable_in_project(self._window, config_name)
        self.update_configs()
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
            if any(needed_configs(self._configs.match_view(view, include_disabled=True))):  # type: ignore
                # TODO: cannot observe project setting changes
                # have to check project overrides every session request
                self.update_configs()
                startable_configs = needed_configs(self._configs.match_view(view))  # type: ignore
                for config in startable_configs:
                    debug("window {} requests {} for {}".format(self._window.id(), config.name, file_path))
                    self.start(config, view)  # type: ignore

    def start(self, config: ClientConfig, initiating_view: sublime.View) -> None:
        file_path = initiating_view.file_name() or ''
        if not self._can_start_config(config.name, file_path):
            debug('Already starting on this window:', config.name)
            return
        self._window.status_message("Starting " + config.name + "...")
        try:
            workspace_folders = sorted_workspace_folders(self._workspace.folders, file_path)
            session_type = get_session_type(config.name)
            session = session_type(self, self._settings, workspace_folders, config)
            if self.server_panel_factory:
                session.logger.sink = self._payload_log_sink
            if workspace_folders:
                cwd = workspace_folders[0].path
            elif file_path:
                cwd = os.path.dirname(file_path)
            else:
                cwd = tempfile.gettempdir()
            # WindowLike vs sublime.Window
            session.initialize(create_transport(config, cwd, self._window, session))  # type: ignore
            self._sessions.setdefault(config.name, []).append(session)
            debug("window {} added session {}".format(self._window.id(), config.name))
        except Exception as e:
            message = "\n\n".join([
                "Could not start {}",
                "{}",
                "Server will be disabled for this window"
            ]).format(config.name, str(e))
            self._configs.disable_temporarily(config.name)
            self._sublime.message_dialog(message)

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

    def _payload_log_sink(self, message: str) -> None:
        self._sublime.set_timeout_async(lambda: self.handle_server_message(":", message), 0)

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
