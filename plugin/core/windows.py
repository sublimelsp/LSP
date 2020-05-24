from .configurations import ConfigManager
from .configurations import WindowConfigManager
from .diagnostics import DiagnosticsStorage
from .edit import parse_workspace_edit
from .logging import debug
from .message_request_handler import MessageRequestHandler
from .protocol import Notification, Response
from .rpc import Client, SublimeLogger
from .sessions import Session
from .types import ClientConfig
from .types import ClientStates
from .types import Settings
from .types import view2scope
from .types import ViewLike
from .types import WindowLike
from .typing import Optional, List, Callable, Dict, Any, Deque, Protocol, Generator
from .workspace import disable_in_project
from .workspace import enable_in_project
from .workspace import get_workspace_folders
from .workspace import ProjectFolders
from .workspace import sorted_workspace_folders
from collections import deque
from weakref import ref
from weakref import WeakSet
from weakref import WeakValueDictionary
import sublime


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


def extract_message(params: Any) -> str:
    return params.get("message", "???") if isinstance(params, dict) else "???"


class ViewListenerProtocol(Protocol):

    view = None  # type: sublime.View

    def on_session_initialized(self, session: Session) -> None:
        ...

    def on_session_shutdown(self, session: Session) -> None:
        ...

    def __hash__(self) -> int:
        ...


class WindowManager(object):
    def __init__(
        self,
        window: WindowLike,
        workspace: ProjectFolders,
        settings: Settings,
        configs: WindowConfigManager,
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
        self.server_panel_factory = server_panel_factory
        self._sessions = {}  # type: Dict[str, WeakSet[Session]]
        self._next_initialize_views = list()  # type: List[ViewLike]
        self._start_session = session_starter
        self._sublime = sublime
        self._handlers = handler_dispatcher
        self._restarting = False
        self._is_closing = False
        self._workspace = workspace
        self._pending_listeners = deque()  # type: Deque[ViewListenerProtocol]
        self._listeners = WeakSet()  # type: WeakSet[ViewListenerProtocol]
        self._new_listener = None  # type: Optional[ViewListenerProtocol]
        self._new_session = None  # type: Optional[Session]
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

    def register_listener(self, listener: ViewListenerProtocol) -> None:
        self._pending_listeners.appendleft(listener)
        if self._new_session:
            return
        sublime.set_timeout_async(self._dequeue_listener)

    def unregister_listener(self, listener: ViewListenerProtocol) -> None:
        self._listeners.discard(listener)

    def listeners(self) -> Generator[ViewListenerProtocol, None, None]:
        yield from self._listeners

    def _dequeue_listener(self) -> None:
        listener = None  # type: Optional[ViewListenerProtocol]
        if self._new_listener is not None and self._new_listener.view.is_valid():
            listener = self._new_listener
            self._new_listener = None
        else:
            try:
                listener = self._pending_listeners.pop()
                if not listener.view.is_valid():
                    sublime.set_timeout_async(self._dequeue_listener)
                    return
                self._listeners.add(listener)
            except IndexError:
                # We have handled all pending listeners.
                self._new_session = None
                return
        scope = view2scope(listener.view)
        file_name = listener.view.file_name() or ''
        if self._new_session:
            self._sessions.setdefault(self._new_session.config.name, WeakSet()).add(self._new_session)
        if listener.view in self._workspace:
            for sessions in self._sessions.values():
                for session in sessions:
                    if session.config.match_document(scope):
                        if session.handles_path(file_name):
                            listener.on_session_initialized(session)
                            break
        else:
            for sessions in self._sessions.values():
                for session in sessions:
                    if session.config.match_document(scope):
                        listener.on_session_initialized(session)
                        break
        self._new_session = None
        config = self._needed_config(listener.view)
        if config:
            self._new_listener = listener
            self._start_client(config, file_name)
        else:
            self._new_listener = None

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
        for listener in self._listeners:
            self._pending_listeners.appendleft(listener)
        self._listeners.clear()
        if not self._new_session:
            sublime.set_timeout_async(self._dequeue_listener)

    def disable_config(self, config_name: str) -> None:
        disable_in_project(self._window, config_name)
        self.update_configs()
        self.end_config_sessions(config_name)

    def _needed_config(self, view: sublime.View) -> Optional[ClientConfig]:
        configs = self._configs.match_view(view)
        if view in self._workspace:
            for config in configs:
                handled = False
                sessions = self._sessions.get(config.name, WeakSet())
                for session in sessions:
                    if session.handles_path(view.file_name() or ''):
                        handled = True
                        break
                if not handled:
                    return config
        else:
            for config in configs:
                if config.name in self._sessions:
                    continue
                return config
        return None

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
            sublime.message_dialog(message)
            # Continue with handling pending listeners
            self._new_session = None
            sublime.set_timeout_async(self._dequeue_listener)

        if session:
            debug("window {} added session {}".format(self._window.id(), config.name))
            self._new_session = session

    def _handle_message_request(self, params: dict, source: str, client: Client, request_id: Any) -> None:
        handler = MessageRequestHandler(self._window.active_view(), client, request_id, params, source)  # type: ignore
        handler.show()

    def restart_sessions(self) -> None:
        self._restarting = True
        self.end_sessions()

    def end_sessions(self) -> None:
        for config_name in list(self._sessions):
            self.end_config_sessions(config_name)

    def end_config_sessions(self, config_name: str) -> None:
        config_sessions = self._sessions.pop(config_name, WeakSet())
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

        self._window.status_message("{} initialized".format(session.config.name))
        sublime.set_timeout_async(self._dequeue_listener)

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

    def _handle_post_exit(self, config_name: str) -> None:
        for view in self._window.views():
            file_name = view.file_name()
            if file_name:
                self.diagnostics.remove(file_name, config_name)
        debug("session", config_name, "ended")

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
    def __init__(self, configs: ConfigManager,
                 session_starter: Callable, sublime: Any, handler_dispatcher: LanguageHandlerListener) -> None:
        self._windows = WeakValueDictionary()  # type: WeakValueDictionary[int, WindowManager]
        self._configs = configs
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
            diagnostics_ui = self._diagnostics_ui_class(window) if self._diagnostics_ui_class else None
            state = WindowManager(
                window=window,
                workspace=workspace,
                settings=self._settings,
                configs=window_configs,
                diagnostics=DiagnosticsStorage(diagnostics_ui),
                session_starter=self._session_starter,
                sublime=self._sublime,
                handler_dispatcher=self._handler_dispatcher,
                server_panel_factory=self._server_panel_factory)
            self._windows[window.id()] = state
        return state
