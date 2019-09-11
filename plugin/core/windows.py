from .diagnostics import WindowDiagnostics, DiagnosticsUpdate
from .events import global_events
from .logging import debug, server_log
from .types import ClientStates, ClientConfig, WindowLike, ViewLike, LanguageConfig, config_supports_syntax
from .protocol import Notification, Response
from .edit import parse_workspace_edit
from .sessions import Session
from .url import filename_to_uri
from .workspace import get_project_path, get_active_view_path
from .rpc import Client
import threading
try:
    from typing_extensions import Protocol
    from typing import Optional, List, Callable, Dict, Any, Iterator
    from types import ModuleType
    assert Optional and List and Callable and Dict and Session and Any and ModuleType and Iterator
    assert LanguageConfig
except ImportError:
    pass
    Protocol = object  # type: ignore


class ConfigRegistry(Protocol):
    # todo: calls config_for_scope immediately.
    all = []  # type: List[ClientConfig]

    def is_supported(self, view: ViewLike) -> bool:
        ...

    def scope_configs(self, view: ViewLike, point: 'Optional[int]' = None) -> 'Iterator[ClientConfig]':
        ...

    def syntax_configs(self, view: ViewLike) -> 'List[ClientConfig]':
        ...

    def syntax_supported(self, view: ViewLike) -> bool:
        ...

    def syntax_config_languages(self, view: ViewLike) -> 'Dict[str, LanguageConfig]':
        ...

    def update(self, configs: 'List[ClientConfig]') -> None:
        ...

    def disable(self, config_name: str) -> None:
        ...


class GlobalConfigs(Protocol):
    def for_window(self, window: WindowLike) -> ConfigRegistry:
        ...


class DocumentHandler(Protocol):
    def add_session(self, session) -> None:
        ...

    def remove_session(self, config_name: str) -> None:
        ...

    def handle_view_opened(self, view: ViewLike) -> None:
        ...

    def reset(self) -> None:
        ...


def get_active_views(window: WindowLike):
    views = list()  # type: List[ViewLike]
    num_groups = window.num_groups()
    for group in range(0, num_groups):
        view = window.active_view_in_group(group)
        if window.active_group() == group:
            views.insert(0, view)
        else:
            views.append(view)

    return views


class DocumentState:
    """Stores version count for documents open in a language service"""
    def __init__(self, path: str) -> 'None':
        self.path = path
        self.version = 0

    def inc_version(self):
        self.version += 1
        return self.version


class DocumentHandlerFactory(object):
    def __init__(self, sublime, settings):
        self._sublime = sublime
        self._settings = settings

    def for_window(self, window: 'WindowLike', configs: 'ConfigRegistry'):
        return WindowDocumentHandler(self._sublime, self._settings, window, global_events, configs)


class WindowDocumentHandler(object):
    def __init__(self, sublime, settings, window, events, configs):
        self._sublime = sublime
        self._settings = settings
        self._configs = configs
        self._window = window
        self._document_states = dict()  # type: Dict[str, DocumentState]
        self._pending_buffer_changes = dict()  # type: Dict[int, Dict]
        self._sessions = dict()  # type: Dict[str, Session]
        events.subscribe('view.on_load_async', self.handle_view_opened)
        events.subscribe('view.on_activated_async', self.handle_view_opened)
        events.subscribe('view.on_modified', self.handle_view_modified)
        events.subscribe('view.on_purge_changes', self.purge_changes)
        events.subscribe('view.on_post_save_async', self.handle_view_saved)
        events.subscribe('view.on_close', self.handle_view_closed)

    def add_session(self, session: Session):
        self._sessions[session.config.name] = session
        self._notify_open_documents(session)

    def remove_session(self, config_name: str):
        if config_name in self._sessions:
            del self._sessions[config_name]

    def reset(self) -> None:
        for view in self._window.views():
            self.detach_view(view)
        self._document_states.clear()

    def get_document_state(self, path: str) -> DocumentState:
        if path not in self._document_states:
            self._document_states[path] = DocumentState(path)
        return self._document_states[path]

    def has_document_state(self, path: str) -> bool:
        return path in self._document_states

    def _get_applicable_sessions(self, view: ViewLike, notification_type: 'Optional[str]'=None):
        sessions = []  # type: List[Session]
        syntax = view.settings().get("syntax")
        for config_name, session in self._sessions.items():
            if config_supports_syntax(session.config, syntax):
                if not notification_type or self._session_supports_notification(session, notification_type):
                    sessions.append(session)
        return sessions

    def _session_supports_notification(self, session: 'Session', notification_type: str) -> bool:
        """
            openClose: boolean
            change: 0 (none), 1 (full), 2 (incremental)
            willSave: boolean
            willSaveWaitUntil: boolean
            save: {includeText: boolean}
        """
        sync_options = session.capabilities.get('textDocumentSync')

        # if a TextDocumentSyncOptions object was sent, we can disable some notifications
        if isinstance(sync_options, dict):
            return bool(sync_options.get(notification_type))

        # otherwise we send them all.
        return True

    def _notify_open_documents(self, session: Session) -> None:
        for file_name in list(self._document_states):
            view = self._window.find_open_file(file_name)
            if view:
                syntax = view.settings().get("syntax")
                if config_supports_syntax(session.config, syntax):
                    sessions = self._get_applicable_sessions(view)
                    self._attach_view(view, sessions)
                    self._notify_did_open(view, session)

    def _is_supported_view(self, view: ViewLike) -> bool:
        return self._configs.syntax_supported(view)

    def _config_languages(self, view: ViewLike) -> 'Dict[str, LanguageConfig]':
        return self._configs.syntax_config_languages(view)

    def _attach_view(self, view: ViewLike, sessions: 'List[Session]'):
        view.settings().set("show_definitions", False)
        if self._settings.show_view_status:
            view.set_status("lsp_clients", ", ".join(session.config.name for session in sessions))

    def detach_view(self, view: ViewLike):
        view.settings().erase("show_definitions")
        view.set_status("lsp_clients", "")

    def _view_language(self, view: ViewLike, config_name: str) -> 'Optional[str]':
        languages = view.settings().get('lsp_language')
        return languages.get(config_name) if languages else None

    def _set_view_languages(self, view: ViewLike, config_languages: 'Dict[str, LanguageConfig]') -> None:
        languages = {}
        for config_name, language in config_languages.items():
            languages[config_name] = language.id
        view.settings().set('lsp_language', languages)
        view.settings().set('lsp_active', True)

    def handle_view_opened(self, view: ViewLike):
        file_name = view.file_name()
        if file_name and view.window() == self._window:
            if not self.has_document_state(file_name):
                config_languages = self._config_languages(view)
                if len(config_languages) > 0:
                    # always register a supported document
                    self.get_document_state(file_name)
                    self._set_view_languages(view, config_languages)

                    # the sessions may not be available yet,
                    # the document will get synced when a session is added.
                    sessions = self._get_applicable_sessions(view)
                    self._attach_view(view, sessions)
                    for session in sessions:
                        if self._session_supports_notification(session, 'openClose'):
                            self._notify_did_open(view, session)

    def _notify_did_open(self, view: ViewLike, session: Session) -> None:
        file_name = view.file_name()
        if file_name:
            ds = self.get_document_state(file_name)
            params = {
                "textDocument": {
                    "uri": filename_to_uri(file_name),
                    "languageId": self._view_language(view, session.config.name),
                    "text": view.substr(self._sublime.Region(0, view.size())),
                    "version": ds.version
                }
            }
            session.client.send_notification(Notification.didOpen(params))

    def handle_view_closed(self, view: ViewLike):
        file_name = view.file_name()
        if file_name in self._document_states:
            del self._document_states[file_name]
            for session in self._get_applicable_sessions(view, 'openClose'):
                debug('closing', file_name, session.config.name)
                if session.client:
                    params = {"textDocument": {"uri": filename_to_uri(file_name)}}
                    session.client.send_notification(Notification.didClose(params))

    def handle_view_saved(self, view: ViewLike):
        file_name = view.file_name()
        if view.window() == self._window:
            if file_name in self._document_states:
                for session in self._get_applicable_sessions(view, 'save'):
                    if session.client:
                        params = {"textDocument": {"uri": filename_to_uri(file_name)}}
                        session.client.send_notification(Notification.didSave(params))
            else:
                debug('document not tracked', file_name)

    def handle_view_modified(self, view: ViewLike):
        if view.window() == self._window:
            buffer_id = view.buffer_id()
            buffer_version = 1
            pending_buffer = None
            if buffer_id in self._pending_buffer_changes:
                pending_buffer = self._pending_buffer_changes[buffer_id]
                buffer_version = pending_buffer["version"] + 1
                pending_buffer["version"] = buffer_version
            else:
                self._pending_buffer_changes[buffer_id] = {
                    "view": view,
                    "version": buffer_version
                }

            self._sublime.set_timeout_async(
                lambda: self.purge_did_change(buffer_id, buffer_version), 500)

    def purge_changes(self, view: ViewLike):
        self.purge_did_change(view.buffer_id())

    def purge_did_change(self, buffer_id: int, buffer_version=None):
        if buffer_id not in self._pending_buffer_changes:
            return

        pending_buffer = self._pending_buffer_changes.get(buffer_id)

        if pending_buffer:
            if buffer_version is None or buffer_version == pending_buffer["version"]:
                self.notify_did_change(pending_buffer["view"])

    def notify_did_change(self, view: ViewLike):
        file_name = view.file_name()
        if file_name and view.window() == self._window:
            # ensure view is opened.
            if not self.has_document_state(file_name):
                self.handle_view_opened(view)

            if view.buffer_id() in self._pending_buffer_changes:
                del self._pending_buffer_changes[view.buffer_id()]

                for session in self._get_applicable_sessions(view, 'change'):
                    if session.client:
                        document_state = self.get_document_state(file_name)
                        uri = filename_to_uri(file_name)
                        params = {
                            "textDocument": {
                                "uri": uri,
                                "version": document_state.inc_version(),
                            },
                            "contentChanges": [{
                                "text": view.substr(self._sublime.Region(0, view.size()))
                            }]
                        }
                        session.client.send_notification(Notification.didChange(params))


class WindowManager(object):
    def __init__(self, window: WindowLike, configs: ConfigRegistry, documents: DocumentHandler,
                 diagnostics: WindowDiagnostics, session_starter: 'Callable', sublime: 'Any',
                 handler_dispatcher, on_closed: 'Optional[Callable]' = None) -> None:

        # to move here:
        # configurations.py: window_client_configs and all references
        self._window = window
        self._configs = configs
        self._diagnostics = diagnostics
        self._documents = documents
        self._sessions = dict()  # type: Dict[str, Session]
        self._start_session = session_starter
        self._sublime = sublime
        self._handlers = handler_dispatcher
        self._restarting = False
        self._project_path = get_project_path(self._window)
        self._projectless_root_path = None  # type: Optional[str]
        self._diagnostics.set_on_updated(
            lambda file_path, client_name:
                global_events.publish("document.diagnostics",
                                      DiagnosticsUpdate(self._window, client_name, file_path)))
        self._on_closed = on_closed
        self._is_closing = False
        self._initialization_lock = threading.Lock()

    def get_session(self, config_name: str) -> 'Optional[Session]':
        return self._sessions.get(config_name)

    def _is_session_ready(self, config_name: str):
        if config_name not in self._sessions:
            return False

        if self._sessions[config_name].state == ClientStates.READY:
            return True

        return False

    def _can_start_config(self, config_name: str):
        return config_name not in self._sessions

    def update_configs(self, configs: 'List[ClientConfig]') -> None:
        self._configs.update(configs)

    def start_active_views(self):
        active_views = get_active_views(self._window)
        debug('window {} starting {} initial views'.format(self._window.id(), len(active_views)))
        for view in active_views:
            if view.file_name():
                self._initialize_on_open(view)
                self._documents.handle_view_opened(view)

    def activate_view(self, view: ViewLike):
        # TODO: we can shortcut here by checking documentstate.
        if self._sessions:
            self._end_old_sessions()
        self._initialize_on_open(view)

    def _initialize_on_open(self, view: ViewLike):
        # have all sessions for this document been started?
        with self._initialization_lock:
            startable_configs = filter(lambda c: c.enabled and c.name not in self._sessions,
                                       self._configs.syntax_configs(view))

            for config in startable_configs:
                debug("window {} requests {} for {}".format(self._window.id(), config.name, view.file_name()))
                self._start_client(config)

    def _start_client(self, config: ClientConfig):
        project_path = self._ensure_project_path()

        if project_path is None:
            debug('Cannot start without a project folder')
            return

        if not self._can_start_config(config.name):
            debug('Already starting on this window:', config.name)
            return

        if not self._handlers.on_start(config.name, self._window):
            return

        self._window.status_message("Starting " + config.name + "...")
        debug("starting in", project_path)
        session = None  # type: Optional[Session]
        try:
            session = self._start_session(
                window=self._window,
                project_path=project_path,
                config=config,
                on_pre_initialize=self._handle_pre_initialize,
                on_post_initialize=self._handle_post_initialize,
                on_post_exit=self._handle_post_exit)
        except Exception as e:
            message = "\n\n".join([
                "Could not start {}",
                "{}",
                "Server will be disabled for this window"
            ]).format(config.name, str(e))

            self._configs.disable(config.name)
            self._sublime.message_dialog(message)

        if session:
            debug("window {} added session {}".format(self._window.id(), config.name))
            self._sessions[config.name] = session

    def _handle_message_request(self, params: dict, client: Client, request_id: int) -> None:
        actions = params.get("actions", [])
        titles = list(action.get("title") for action in actions)

        def send_user_choice(index):
            # when noop; nothing was selected e.g. the user pressed escape
            result = None
            if index != -1:
                result = {"title": titles[index]}
            response = Response(request_id, result)
            client.send_response(response)

        if actions:
            self._sublime.active_window().show_quick_panel(titles, send_user_choice)

    def restart_sessions(self):
        self._restarting = True
        self.end_sessions()

    def end_sessions(self) -> None:
        self._documents.reset()
        for config_name in list(self._sessions):
            self.end_session(config_name)

    def end_session(self, config_name: str) -> None:
        if config_name in self._sessions:
            debug("unloading session", config_name)
            self._sessions[config_name].end()

    def _ensure_project_path(self) -> 'Optional[str]':
        if self._project_path is None:
            self._project_path = get_project_path(self._window)
            if self._project_path is None and self._projectless_root_path is None:
                # the projectless fallback will only be set once per window.
                self._projectless_root_path = get_active_view_path(self._window)
        return self._project_path or self._projectless_root_path

    def get_project_path(self) -> 'Optional[str]':
        return self._project_path or self._projectless_root_path

    def _end_old_sessions(self):
        current_project_path = get_project_path(self._window)
        if current_project_path != self._project_path:
            debug('project path changed, ending existing sessions')
            debug('new path = {}'.format(current_project_path))
            self.end_sessions()
            self._project_path = current_project_path

    def _apply_workspace_edit(self, params: 'Dict[str, Any]', client: Client, request_id: int) -> None:
        edit = params.get('edit', dict())
        changes = parse_workspace_edit(edit)
        self._window.run_command('lsp_apply_workspace_edit', {'changes': changes})
        # TODO: We should ideally wait for all changes to have been applied.
        # This however seems overly complicated, because we have to bring along a string representation of the
        # client through the sublime-command invocations (as well as the request ID, but that is easy), and then
        # reconstruct/get the actual Client object back. Maybe we can (ab)use our homebrew event system for this?
        client.send_response(Response(request_id, {"applied": True}))

    def _handle_pre_initialize(self, session: 'Session') -> None:
        client = session.client
        client.set_crash_handler(lambda: self._handle_server_crash(session.config))
        client.set_error_display_handler(self._window.status_message)

        client.on_request(
            "window/showMessageRequest",
            lambda params, request_id: self._handle_message_request(params, client, request_id))

        client.on_notification(
            "window/showMessage",
            lambda params: self._sublime.message_dialog(params.get("message")))

        client.on_notification(
            "window/logMessage",
            lambda params: server_log(session.config.name, params.get("message", "???") if params else "???"))

    def _handle_post_initialize(self, session: 'Session') -> None:
        client = session.client

        # handle server requests and notifications
        client.on_request(
            "workspace/applyEdit",
            lambda params, request_id: self._apply_workspace_edit(params, client, request_id))

        client.on_notification(
            "textDocument/publishDiagnostics",
            lambda params: self._diagnostics.handle_client_diagnostics(session.config.name, params))

        self._handlers.on_initialized(session.config.name, self._window, client)

        client.send_notification(Notification.initialized())

        document_sync = session.capabilities.get("textDocumentSync")
        if document_sync:
            self._documents.add_session(session)

        global_events.subscribe('view.on_close', lambda view: self._handle_view_closed(view, session))

        if session.config.settings:
            configParams = {
                'settings': session.config.settings
            }
            client.send_notification(Notification.didChangeConfiguration(configParams))

        self._window.status_message("{} initialized".format(session.config.name))

    def _handle_view_closed(self, view, session):
        if view.file_name():
            if not self._is_closing:
                if not self._window.is_valid():
                    # try to detect close synchronously (for quitting)
                    self._handle_window_closed()
                else:
                    # in case the window is invalidated after the last view is closed
                    self._sublime.set_timeout_async(lambda: self._check_window_closed(), 100)

    def _check_window_closed(self):
        # debug('window {} check window closed closing={}, valid={}'.format(
        # self._window.id(), self._is_closing, self._window.is_valid()))

        if not self._is_closing and not self._window.is_valid():
            self._handle_window_closed()

    def _handle_window_closed(self):
        debug('window {} closed, ending sessions'.format(self._window.id()))
        self._is_closing = True
        self.end_sessions()

    def _handle_all_sessions_ended(self):
        debug('clients for window {} unloaded'.format(self._window.id()))
        if self._restarting:
            debug('window {} sessions unloaded - restarting'.format(self._window.id()))
            self.start_active_views()
        elif not self._window.is_valid():
            debug('window {} closed and sessions unloaded'.format(self._window.id()))
            if self._on_closed:
                self._on_closed()

    def _handle_post_exit(self, config_name: str) -> None:
        self._documents.remove_session(config_name)
        del self._sessions[config_name]
        for view in self._window.views():
            file_name = view.file_name()
            if file_name:
                self._diagnostics.remove(file_name, config_name)

        debug("session", config_name, "ended")
        if not self._sessions:
            self._handle_all_sessions_ended()

    def _handle_server_crash(self, config: ClientConfig):
        msg = "Language server {} has crashed, do you want to restart it?".format(config.name)
        result = self._sublime.ok_cancel_dialog(msg, ok_title="Restart")
        if result == self._sublime.DIALOG_YES:
            self.restart_sessions()


class WindowRegistry(object):
    def __init__(self, configs: GlobalConfigs, documents: 'Any',
                 session_starter: 'Callable', sublime: 'Any', handler_dispatcher) -> None:
        self._windows = {}  # type: Dict[int, WindowManager]
        self._configs = configs
        self._documents = documents
        self._session_starter = session_starter
        self._sublime = sublime
        self._handler_dispatcher = handler_dispatcher

    def lookup(self, window: 'Any') -> WindowManager:
        state = self._windows.get(window.id())
        if state is None:
            window_configs = self._configs.for_window(window)
            window_documents = self._documents.for_window(window, window_configs)
            state = WindowManager(window, window_configs, window_documents, WindowDiagnostics(), self._session_starter,
                                  self._sublime, self._handler_dispatcher, lambda: self._on_closed(window))
            self._windows[window.id()] = state
        return state

    def _on_closed(self, window: WindowLike) -> None:
        if window.id() in self._windows:
            del self._windows[window.id()]
