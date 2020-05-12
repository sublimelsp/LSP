from .diagnostics import DiagnosticsStorage
from .edit import parse_workspace_edit
from .logging import debug
from .message_request_handler import MessageRequestHandler
from .protocol import Notification, Response, TextDocumentSyncKindNone, TextDocumentSyncKindFull
from .rpc import Client, SublimeLogger
from .sessions import Session
from .types import ClientConfig
from .types import ClientStates
from .types import config_supports_syntax
from .types import ConfigRegistry
from .types import GlobalConfigs
from .types import LanguageConfig
from .types import Settings
from .types import ViewLike
from .types import WindowLike
from .typing import Optional, List, Callable, Dict, Any, Protocol, Set, Iterable
from .views import did_change, did_close, did_open, did_save, will_save
from .workspace import disable_in_project
from .workspace import enable_in_project
from .workspace import get_workspace_folders
from .workspace import ProjectFolders
from .workspace import sorted_workspace_folders
from weakref import ref
from weakref import WeakValueDictionary
import sublime
import threading


class SublimeLike(Protocol):

    def set_timeout_async(self, f: Callable, timeout_ms: int = 0) -> None:
        ...

    def Region(self, a: int, b: int) -> 'Any':
        ...


class LanguageHandlerListener(Protocol):

    def on_start(self, config_name: str, window: WindowLike) -> bool:
        ...

    def on_initialized(self, config_name: str, window: WindowLike, client: Client) -> None:
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
                   configs: ConfigRegistry) -> DocumentHandler:
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
                 configs: ConfigRegistry) -> None:
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
        syntax = view.settings().get("syntax")

        for config_name, config_sessions in self._sessions.items():
            for session in config_sessions:
                if config_supports_syntax(session.config, syntax):
                    if session.handles_path(view.file_name()):
                        sessions.append(session)

        return sessions

    def _notify_open_documents(self, session: Session) -> None:
        # Note: a copy is made of self._document_states because it may be modified in another thread.
        for file_name in list(self._document_states):
            if session.handles_path(file_name):
                view = self._window.find_open_file(file_name)
                if view:
                    syntax = view.settings().get("syntax")
                    if config_supports_syntax(session.config, syntax):
                        sessions = self._get_applicable_sessions(view)
                        self._attach_view(view, sessions)
                        for session in sessions:
                            if session.should_notify_did_open():
                                self._notify_did_open(view, session)

    def _is_supported_view(self, view: ViewLike) -> bool:
        return self._configs.syntax_supported(view)

    def _config_languages(self, view: ViewLike) -> Dict[str, LanguageConfig]:
        return self._configs.syntax_config_languages(view)

    def _attach_view(self, view: ViewLike, sessions: List[Session]) -> None:
        view.settings().set("show_definitions", False)
        if self._settings.show_view_status:
            view.set_status("lsp_clients", ", ".join(session.config.name for session in sessions))

    def detach_view(self, view: ViewLike) -> None:
        view.settings().erase("show_definitions")
        view.set_status("lsp_clients", "")

    def _view_language(self, view: ViewLike, config_name: str) -> str:
        return view.settings().get('lsp_language')[config_name]

    def _set_view_languages(self, view: ViewLike, config_languages: Dict[str, LanguageConfig]) -> None:
        languages = {}
        for config_name, language in config_languages.items():
            languages[config_name] = language.id
        view.settings().set('lsp_language', languages)
        view.settings().set('lsp_active', True)

    def handle_did_open(self, view: ViewLike) -> None:
        file_name = view.file_name()
        if file_name and file_name not in self._document_states:
            config_languages = self._config_languages(view)
            if len(config_languages) > 0:
                # always register a supported document
                self._document_states.add(file_name)
                self._set_view_languages(view, config_languages)

                # the sessions may not be available yet,
                # the document will get synced when a session is added.
                sessions = self._get_applicable_sessions(view)
                self._attach_view(view, sessions)
                for session in sessions:
                    if session.should_notify_did_open():
                        self._notify_did_open(view, session)

    def _notify_did_open(self, view: ViewLike, session: Session) -> None:
        language_id = self._view_language(view, session.config.name)
        if session.client:
            # mypy: expected sublime.View, got ViewLike
            session.client.send_notification(did_open(view, language_id))  # type: ignore

    def handle_did_close(self, view: ViewLike) -> None:
        file_name = view.file_name() or ""
        try:
            self._document_states.remove(file_name)
        except KeyError:
            return
        # mypy: expected sublime.View, got ViewLike
        notification = did_close(view)  # type: ignore
        for session in self._get_applicable_sessions(view):
            if session.client and session.should_notify_did_close():
                session.client.send_notification(notification)

    def handle_will_save(self, view: ViewLike, reason: int) -> None:
        file_name = view.file_name()
        if file_name in self._document_states:
            for session in self._get_applicable_sessions(view):
                if session.client and session.should_notify_will_save():
                    # mypy: expected sublime.View, got ViewLike
                    session.client.send_notification(will_save(view, reason))  # type: ignore

    def handle_did_save(self, view: ViewLike) -> None:
        file_name = view.file_name()
        if file_name in self._document_states:
            self.purge_changes(view)
            for session in self._get_applicable_sessions(view):
                if session.client:
                    send_did_save, include_text = session.should_notify_did_save()
                    if send_did_save:
                        # mypy: expected sublime.View, got ViewLike
                        session.client.send_notification(did_save(view, include_text))  # type: ignore
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
            if not session.client:
                continue
            sync_kind = session.text_sync_kind()
            if sync_kind == TextDocumentSyncKindNone:
                continue
            changes = None if sync_kind == TextDocumentSyncKindFull else pending_buffer.changes
            # ViewLike vs sublime.View
            notification = did_change(view, changes)  # type: ignore
            session.client.send_notification(notification)


def extract_message(params: Any) -> str:
    return params.get("message", "???") if isinstance(params, dict) else "???"


class WindowManager(object):
    def __init__(
        self,
        window: WindowLike,
        workspace: ProjectFolders,
        settings: Settings,
        configs: ConfigRegistry,
        documents: DocumentHandler,
        diagnostics: DiagnosticsStorage,
        session_starter: Callable,
        sublime: Any,
        handler_dispatcher: LanguageHandlerListener,
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
        self._start_session = session_starter
        self._sublime = sublime
        self._handlers = handler_dispatcher
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

    def get_sessions(self):
        return list(self._sessions)

    def has_active_sessions(self) -> bool:
        return bool(self._sessions)

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

        def needed_configs(configs: 'List[ClientConfig]') -> 'List[ClientConfig]':
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
            new_configs = needed_configs(self._configs.syntax_configs(view, include_disabled=True))

            if any(new_configs):
                # TODO: cannot observe project setting changes
                # have to check project overrides every session request
                self.update_configs()

                startable_configs = needed_configs(self._configs.syntax_configs(view))

                for config in startable_configs:

                    debug("window {} requests {} for {}".format(self._window.id(), config.name, file_path))
                    self._start_client(config, file_path)

    def _start_client(self, config: ClientConfig, file_path: str) -> None:
        if not self._can_start_config(config.name, file_path):
            debug('Already starting on this window:', config.name)
            return

        if not self._handlers.on_start(config.name, self._window):
            return

        self._window.status_message("Starting " + config.name + "...")
        session = None  # type: Optional[Session]
        workspace_folders = sorted_workspace_folders(self._workspace.folders, file_path)
        try:
            session = self._start_session(
                self._window,                  # window
                workspace_folders,             # workspace_folders
                config,                        # config
                self._handle_pre_initialize,   # on_pre_initialize
                self._handle_post_initialize,  # on_post_initialize
                self._handle_post_exit,        # on_post_exit
                lambda msg: self._handle_stderr_log(config.name, msg))  # on_stderr_log
        except Exception as e:
            message = "\n\n".join([
                "Could not start {}",
                "{}",
                "Server will be disabled for this window"
            ]).format(config.name, str(e))

            self._configs.disable_temporarily(config.name)
            self._sublime.message_dialog(message)

        if session:
            debug("window {} added session {}".format(self._window.id(), config.name))
            self._sessions.setdefault(config.name, []).append(session)

    def _handle_message_request(self, params: dict, source: str, client: Client, request_id: Any) -> None:
        handler = MessageRequestHandler(self._window.active_view(), client, request_id, params, source)  # type: ignore
        handler.show()

    def restart_session(self, config_name: str) -> None:
        self._restarting = True
        self.documents.reset()
        self.end_config_sessions(config_name=config_name)

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
            debug("unloading session", config_name)
            session.end()

    def get_project_path(self, file_path: str) -> Optional[str]:
        candidate = None  # type: Optional[str]
        for folder in self._workspace.folders:
            if file_path.startswith(folder):
                if candidate is None or len(folder) > len(candidate):
                    candidate = folder
        return candidate

    def _apply_workspace_edit(self, params: Dict[str, Any], client: Client, request_id: int) -> None:
        edit = params.get('edit', dict())
        changes = parse_workspace_edit(edit)
        self._window.run_command('lsp_apply_workspace_edit', {'changes': changes})
        # TODO: We should ideally wait for all changes to have been applied.
        # This however seems overly complicated, because we have to bring along a string representation of the
        # client through the sublime-command invocations (as well as the request ID, but that is easy), and then
        # reconstruct/get the actual Client object back. Maybe we can (ab)use our homebrew event system for this?
        client.send_response(Response(request_id, {"applied": True}))

    def _payload_log_sink(self, message: str) -> None:
        self._sublime.set_timeout_async(lambda: self._handle_server_message(":", message), 0)

    def _handle_pre_initialize(self, session: Session) -> None:
        client = session.client
        client.set_crash_handler(lambda: self._handle_server_crash(session.config))
        client.set_error_display_handler(self._window.status_message)

        if self.server_panel_factory and isinstance(client.logger, SublimeLogger):
            client.logger.server_name = session.config.name
            client.logger.sink = self._payload_log_sink

        client.on_request(
            "window/showMessageRequest",
            lambda params, request_id: self._handle_message_request(params, session.config.name, client, request_id))

        client.on_notification(
            "window/showMessage",
            lambda params: self._handle_show_message(session.config.name, params))

        client.on_notification(
            "window/logMessage",
            lambda params: self._handle_log_message(session.config.name, params))

    def _handle_post_initialize(self, session: Session) -> None:

        # handle server requests and notifications
        session.on_request(
            "workspace/applyEdit",
            lambda params, request_id: self._apply_workspace_edit(params, session.client, request_id))

        session.on_request(
            "window/workDoneProgress/create",
            lambda params, request_id: self._receive_progress_token(params, session.client, request_id))

        session.on_notification(
            "textDocument/publishDiagnostics",
            lambda params: self.diagnostics.receive(session.config.name, params))

        session.on_notification(
            "$/progress",
            lambda params: self._handle_progress_notification(params))

        self._handlers.on_initialized(session.config.name, self._window, session.client)

        session.client.send_notification(Notification.initialized())

        if session.has_capability("textDocumentSync"):
            self.documents.add_session(session)
        self._window.status_message("{} initialized".format(session.config.name))

        self._open_pending_views()

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

    def _receive_progress_token(self, params: Dict[str, Any], client: Client, request_id: Any) -> None:
        self._progress[params['token']] = dict()
        client.send_response(Response(request_id, None))

    def _handle_progress_notification(self, params: Dict[str, Any]) -> None:
        token = params['token']
        if token not in self._progress:
            debug('unknown $/progress token: {}'.format(token))
            return
        value = params['value']
        if value['kind'] == 'begin':
            self._progress[token]['title'] = value['title']  # mandatory
            self._progress[token]['message'] = value.get('message')  # optional
            self._window.status_message(self._progress_string(token, value))
        elif value['kind'] == 'report':
            self._window.status_message(self._progress_string(token, value))
        elif value['kind'] == 'end':
            if value.get('message'):
                status_msg = self._progress[token]['title'] + ': ' + value['message']
                self._window.status_message(status_msg)
            self._progress.pop(token, None)

    def _progress_string(self, token: Any, value: Dict[str, Any]) -> str:
        status_msg = self._progress[token]['title']
        progress_message = value.get('message')  # optional
        progress_percentage = value.get('percentage')  # optional
        if progress_message:
            self._progress[token]['message'] = progress_message
            status_msg += ': ' + progress_message
        elif self._progress[token]['message']:  # reuse last known message if not present
            status_msg += ': ' + self._progress[token]['message']
        if progress_percentage:
            fmt = ' ({:.1f}%)' if isinstance(progress_percentage, float) else ' ({}%)'
            status_msg += fmt.format(progress_percentage)
        return status_msg

    def _handle_window_closed(self) -> None:
        debug('window {} closed, ending sessions'.format(self._window.id()))
        self._is_closing = True
        self.end_sessions()

    def _handle_all_sessions_ended(self) -> None:
        debug('clients for window {} unloaded'.format(self._window.id()))
        if self._restarting:
            debug('window {} sessions unloaded - restarting'.format(self._window.id()))
            self.start_active_views()

    def _handle_post_exit(self, config_name: str) -> None:
        self.documents.remove_session(config_name)
        for view in self._window.views():
            file_name = view.file_name()
            if file_name:
                self.diagnostics.remove(file_name, config_name)

        debug("session", config_name, "ended")
        if not self._sessions:
            self._handle_all_sessions_ended()

    def _handle_server_crash(self, config: ClientConfig) -> None:
        msg = "Language server {} has crashed, do you want to restart it?".format(config.name)
        result = self._sublime.ok_cancel_dialog(msg, ok_title="Restart")
        if result == self._sublime.DIALOG_YES:
            self.restart_sessions()

    def _handle_server_message(self, name: str, message: str) -> None:
        if not self.server_panel_factory:
            return
        panel = self.server_panel_factory(self._window)
        if not panel:
            return debug("no server panel for window", self._window.id())
        panel.run_command("lsp_update_server_panel", {"prefix": name, "message": message})

    def _handle_log_message(self, name: str, params: Any) -> None:
        self._handle_server_message(name, extract_message(params))

    def _handle_stderr_log(self, name: str, message: str) -> None:
        if self._settings.log_stderr:
            self._handle_server_message(name, message)

    def _handle_show_message(self, name: str, params: Any) -> None:
        self._sublime.status_message("{}: {}".format(name, extract_message(params)))


class WindowRegistry(object):
    def __init__(self, configs: GlobalConfigs, documents: Any,
                 session_starter: Callable, sublime: Any, handler_dispatcher: LanguageHandlerListener) -> None:
        self._windows = WeakValueDictionary()  # type: WeakValueDictionary[int, WindowManager]
        self._configs = configs
        self._documents = documents
        self._session_starter = session_starter
        self._sublime = sublime
        self._handler_dispatcher = handler_dispatcher
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
                session_starter=self._session_starter,
                sublime=self._sublime,
                handler_dispatcher=self._handler_dispatcher,
                server_panel_factory=self._server_panel_factory)
            self._windows[window.id()] = state
        return state
