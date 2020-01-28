from .diagnostics import DiagnosticsStorage
from .edit import parse_workspace_edit
from .logging import debug
from .protocol import Notification, Response
from .rpc import Client
from .sessions import Session, InitializeError
from .types import ClientConfig
from .types import config_supports_syntax
from .types import ConfigRegistry
from .types import GlobalConfigs
from .types import LanguageConfig
from .types import Settings
from .types import ViewLike
from .types import WindowLike
from .typing import Optional, List, Callable, Dict, Any, Protocol
from .url import filename_to_uri
from .workspace import get_workspace_folders
from .workspace import disable_in_project
from .workspace import enable_in_project
from .workspace import ProjectFolders
from .workspace import sorted_workspace_folders
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

    def handle_view_opened(self, view: ViewLike) -> None:
        ...

    def handle_view_modified(self, view: ViewLike) -> None:
        ...

    def purge_changes(self, view: ViewLike) -> None:
        ...

    def handle_view_saved(self, view: ViewLike) -> None:
        ...

    def handle_view_closed(self, view: ViewLike) -> None:
        ...

    def has_document_state(self, file_name: str) -> bool:
        ...


def get_active_views(window: WindowLike) -> List[ViewLike]:
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

    def __init__(self, path: str) -> None:
        self.path = path
        self.version = 0

    def inc_version(self) -> int:
        self.version += 1
        return self.version


class DocumentHandlerFactory(object):
    def __init__(self, sublime: Any, settings: Settings) -> None:
        self._sublime = sublime
        self._settings = settings

    def for_window(self, window: WindowLike, workspace: ProjectFolders,
                   configs: ConfigRegistry) -> DocumentHandler:
        return WindowDocumentHandler(self._sublime, self._settings, window, workspace, configs)


def nop() -> None:
    pass


class WindowDocumentHandler(object):
    def __init__(self, sublime: Any, settings: Settings, window: WindowLike, workspace: ProjectFolders,
                 configs: ConfigRegistry) -> None:
        self._sublime = sublime
        self._settings = settings
        self._configs = configs
        self._window = window
        self._document_states = dict()  # type: Dict[str, DocumentState]
        self._pending_buffer_changes = dict()  # type: Dict[int, Dict]
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

    def get_document_state(self, path: str) -> DocumentState:
        if path not in self._document_states:
            self._document_states[path] = DocumentState(path)
        return self._document_states[path]

    def has_document_state(self, path: str) -> bool:
        return path in self._document_states

    def _get_applicable_sessions(self, view: ViewLike, notification_type: Optional[str] = None) -> List[Session]:
        sessions = []  # type: List[Session]
        syntax = view.settings().get("syntax")

        def conditional_append(session: Session) -> None:
            if config_supports_syntax(session.config, syntax):
                if not notification_type or self._session_supports_notification(session, notification_type):
                    sessions.append(session)

        if view in self._workspace:
            for sessions_per_config_name in self._sessions.values():
                for session in sessions_per_config_name:
                    if session.handles_path(view.file_name()):
                        conditional_append(session)
        else:
            for sessions_per_config_name in self._sessions.values():
                assert len(sessions_per_config_name) > 0
                conditional_append(sessions_per_config_name[0])
        return sessions

    def _session_supports_notification(self, session: Session, notification_type: str) -> bool:
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
            notification = sync_options.get(notification_type)
            if notification is None or notification is False:
                return False

        # otherwise we send them all.
        return True

    def _notify_open_documents(self, session: Session) -> None:
        for file_name in list(self._document_states):
            if session.handles_path(file_name):
                view = self._window.find_open_file(file_name)
                if view:
                    syntax = view.settings().get("syntax")
                    if config_supports_syntax(session.config, syntax):
                        sessions = self._get_applicable_sessions(view)
                        self._attach_view(view, sessions)
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

    def _view_language(self, view: ViewLike, config_name: str) -> Optional[str]:
        languages = view.settings().get('lsp_language')
        return languages.get(config_name) if languages else None

    def _set_view_languages(self, view: ViewLike, config_languages: Dict[str, LanguageConfig]) -> None:
        languages = {}
        for config_name, language in config_languages.items():
            languages[config_name] = language.id
        view.settings().set('lsp_language', languages)
        view.settings().set('lsp_active', True)

    def handle_view_opened(self, view: ViewLike) -> None:
        file_name = view.file_name()
        if file_name:
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

    def handle_view_closed(self, view: ViewLike) -> None:
        file_name = view.file_name()
        if file_name in self._document_states:
            del self._document_states[file_name]
            for session in self._get_applicable_sessions(view, 'openClose'):
                debug('closing', file_name, session.config.name)
                if session.client:
                    params = {"textDocument": {"uri": filename_to_uri(file_name)}}
                    session.client.send_notification(Notification.didClose(params))

    def handle_view_saved(self, view: ViewLike) -> None:
        file_name = view.file_name()
        if file_name in self._document_states:
            self.purge_changes(view)
            for session in self._get_applicable_sessions(view, 'save'):
                if session.client:
                    params = {"textDocument": {"uri": filename_to_uri(file_name)}}
                    session.client.send_notification(Notification.didSave(params))
            self.saved()
        else:
            debug('document not tracked', file_name)

    def handle_view_modified(self, view: ViewLike) -> None:
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

    def purge_changes(self, view: ViewLike) -> None:
        self.purge_did_change(view.buffer_id())

    def purge_did_change(self, buffer_id: int, buffer_version: Optional[int] = None) -> None:
        if buffer_id not in self._pending_buffer_changes:
            return

        pending_buffer = self._pending_buffer_changes.get(buffer_id)

        if pending_buffer:
            if buffer_version is None or buffer_version == pending_buffer["version"]:
                self.notify_did_change(pending_buffer["view"])
                self.changed()

    def notify_did_change(self, view: ViewLike) -> None:
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
        on_closed: Optional[Callable] = None,
        server_panel_factory: Optional[Callable] = None
    ) -> None:
        self._window = window
        self._settings = settings
        self._configs = configs
        self.diagnostics = diagnostics
        self.documents = documents
        self.server_panel_factory = server_panel_factory
        self._sessions = dict()  # type: Dict[str, List[Session]]
        self._start_session = session_starter
        self._sublime = sublime
        self._handlers = handler_dispatcher
        self._restarting = False
        self._on_closed = on_closed
        self._is_closing = False
        self._initialization_lock = threading.Lock()
        self._workspace = workspace
        self._workspace.on_changed = self._on_project_changed
        self._workspace.on_switched = self._on_project_switched

    def _on_project_changed(self, folders: List[str]) -> None:
        workspace_folders = get_workspace_folders(self._workspace.folders)
        for config_name in self._sessions:
            for session in self._sessions[config_name]:
                session.update_folders(workspace_folders)

    def _on_project_switched(self, folders: List[str]) -> None:
        debug('project switched - ending all sessions')
        self.end_sessions()

    def get_session(self, config_name: str, file_path: str) -> Optional[Session]:
        try:
            return self._find_session(config_name, file_path)
        except InitializeError as ex:
            self._disable_temporarily(ex.name, ex)
        return None

    def _find_session(self, config_name: str, file_path: str) -> Optional[Session]:
        if file_path in self._workspace:
            sessions = self._sessions.get(config_name, [])
            for session in sessions:
                if session.handles_path(file_path):
                    return session
        else:
            sessions = self._sessions.get(config_name, [])
            if not sessions:
                return None
            return sessions[0]
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
                self.documents.handle_view_opened(view)

    def activate_view(self, view: ViewLike) -> None:
        file_name = view.file_name() or ""
        if not self.documents.has_document_state(file_name):
            self._workspace.update()
            self._initialize_on_open(view)

    def needed_configs(self, file_path: str, configs: List[ClientConfig]) -> List[ClientConfig]:
        new_configs = []
        for c in configs:
            sessions = self._sessions.get(c.name, None)
            if sessions is None:
                new_configs.append(c)
                continue
            assert isinstance(sessions, list)
            assert len(sessions) > 0
            first_session = sessions[0]
            if first_session.supports_workspace_folders():
                # A workspace-aware language server handles any path, both inside and outside the workspace.
                continue
            if file_path in self._workspace:
                if any(s.handles_path(file_path) for s in sessions):
                    # The file_path is inside the workspace, and there's a non-workspace-aware language server that can
                    # handle this path. So no new session is needed.
                    continue
                # There is no non-workspace-aware language that handles this path, but it is inside the workspace. So
                # we must start a new session.
                new_configs.append(c)
                continue
            # We're now dealing with a non-workspace-aware language server, and the file_path is outside the workspace.
            # Let us then take the first language server in the list that shall handle this path.
            # (so no new session is needed).
        return new_configs

    def _initialize_on_open(self, view: ViewLike) -> None:
        file_path = view.file_name() or ""

        # have all sessions for this document been started?
        with self._initialization_lock:
            new_configs = self.needed_configs(file_path, self._configs.syntax_configs(view, include_disabled=True))

            if any(new_configs):
                # TODO: cannot observe project setting changes
                # have to check project overrides every session request
                self.update_configs()

                startable_configs = self.needed_configs(file_path, self._configs.syntax_configs(view))

                for config in startable_configs:

                    debug("window {} requests {} for {}".format(self._window.id(), config.name, file_path))
                    self._start_client(config, file_path)

    def _disable_temporarily(self, name: str, e: Exception) -> None:
        message = "\n\n".join([
            "Could not start {}",
            "{}",
            "Server will be disabled for this window"
        ]).format(name, str(e))
        sessions = self._sessions.pop(name, [])
        self._configs.disable_temporarily(name)
        self._sublime.message_dialog(message)
        for session in sessions:
            session.end()

    def _start_client(self, config: ClientConfig, file_path: str) -> None:
        session = self.get_session(config.name, file_path)
        if session is not None:
            debug(config.name, "was already started")
            return

        if not self._handlers.on_start(config.name, self._window):
            return

        self._window.status_message("Starting " + config.name + "...")
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
            self._disable_temporarily(config.name, e)

        if session:
            debug("window {} added session {}".format(self._window.id(), config.name))
            self._sessions.setdefault(config.name, []).append(session)

    def _handle_message_request(self, params: dict, client: Client, request_id: int) -> None:
        actions = params.get("actions", [])
        titles = list(action.get("title") for action in actions)

        def send_user_choice(index: int) -> None:
            # when noop; nothing was selected e.g. the user pressed escape
            result = None
            if index != -1:
                result = {"title": titles[index]}
            response = Response(request_id, result)
            client.send_response(response)

        if actions:
            self._sublime.active_window().show_quick_panel(titles, send_user_choice)

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

    def _get_session_config(self, params: Dict[str, Any], session: Session, client: Client, request_id: int) -> None:
        items = []  # type: List[Any]
        requested_items = params.get("items") or []
        for requested_item in requested_items:
            items.append(session.config.settings)

        client.send_response(Response(request_id, items))

    def _payload_log_sink(self, message: str) -> None:
        self._sublime.set_timeout_async(lambda: self._handle_server_message(":", message), 0)

    def _handle_pre_initialize(self, session: Session) -> None:
        client = session.client
        client.set_crash_handler(lambda: self._handle_server_crash(session.config))
        client.set_error_display_handler(self._window.status_message)

        if self.server_panel_factory:
            client.logger.server_name = session.config.name
            client.logger.sink = self._payload_log_sink

        client.on_request(
            "window/showMessageRequest",
            lambda params, request_id: self._handle_message_request(params, client, request_id))

        client.on_notification(
            "window/showMessage",
            lambda params: self._handle_show_message(session.config.name, params))

        client.on_notification(
            "window/logMessage",
            lambda params: self._handle_log_message(session.config.name, params))

    def _handle_post_initialize(self, session: Session) -> None:
        client = session.client

        # handle server requests and notifications
        client.on_request(
            "workspace/applyEdit",
            lambda params, request_id: self._apply_workspace_edit(params, client, request_id))

        client.on_request(
            "workspace/configuration",
            lambda params, request_id: self._get_session_config(params, session, client, request_id))

        client.on_notification(
            "textDocument/publishDiagnostics",
            lambda params: self.diagnostics.receive(session.config.name, params))

        self._handlers.on_initialized(session.config.name, self._window, client)

        client.send_notification(Notification.initialized())

        document_sync = session.capabilities.get("textDocumentSync")
        if document_sync:
            self.documents.add_session(session)

        if session.config.settings:
            configParams = {
                'settings': session.config.settings
            }
            client.send_notification(Notification.didChangeConfiguration(configParams))

        self._window.status_message("{} initialized".format(session.config.name))

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
            self.start_active_views()
        elif not self._window.is_valid():
            debug('window {} closed and sessions unloaded'.format(self._window.id()))
            if self._on_closed:
                self._on_closed()

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
        self._windows = {}  # type: Dict[int, WindowManager]
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
                on_closed=lambda: self._on_closed(window),
                server_panel_factory=self._server_panel_factory)
            self._windows[window.id()] = state
        return state

    def _on_closed(self, window: WindowLike) -> None:
        if window.id() in self._windows:
            del self._windows[window.id()]
