from ...third_party import WebsocketServer  # type: ignore
from .configurations import ConfigManager
from .configurations import WindowConfigManager
from .diagnostics import DiagnosticsStorage
from .logging import debug
from .logging import exception_log
from .message_request_handler import MessageRequestHandler
from .panels import update_server_panel
from .protocol import Error
from .rpc import Logger
from .sessions import get_plugin
from .sessions import Manager
from .sessions import Session
from .settings import settings
from .transports import create_transport
from .types import ClientConfig
from .types import Settings
from .typing import Optional, Callable, Any, Dict, Deque, List, Generator
from .views import extract_variables
from .workspace import disable_in_project
from .workspace import enable_in_project
from .workspace import ProjectFolders
from .workspace import sorted_workspace_folders
from abc import ABCMeta
from abc import abstractmethod
from collections import deque
from copy import deepcopy
from time import time
from weakref import ref
from weakref import WeakSet
import json
import sublime
import threading


class AbstractViewListener(metaclass=ABCMeta):

    view = None  # type: sublime.View

    @property
    @abstractmethod
    def manager(self) -> "WindowManager":
        raise NotImplementedError()

    @abstractmethod
    def on_session_initialized_async(self, session: Session) -> None:
        raise NotImplementedError()

    @abstractmethod
    def on_session_shutdown_async(self, session: Session) -> None:
        raise NotImplementedError()


def extract_message(params: Any) -> str:
    return params.get("message", "???") if isinstance(params, dict) else "???"


class WindowManager(Manager):
    def __init__(
        self,
        window: sublime.Window,
        workspace: ProjectFolders,
        settings: Settings,
        configs: WindowConfigManager,
        diagnostics: DiagnosticsStorage,
    ) -> None:
        self._window = window
        self._settings = settings
        self._configs = configs
        self.diagnostics = diagnostics
        self._sessions = WeakSet()  # type: WeakSet[Session]
        self._workspace = workspace
        self._pending_listeners = deque()  # type: Deque[AbstractViewListener]
        self._listeners = WeakSet()  # type: WeakSet[AbstractViewListener]
        self._new_listener = None  # type: Optional[AbstractViewListener]
        self._new_session = None  # type: Optional[Session]

    def on_load_project_async(self) -> None:
        # TODO: Also end sessions that were previously enabled in the .sublime-project, but now disabled or removed
        # from the .sublime-project.
        self.end_sessions_async()
        self._configs.update()
        workspace_folders = self._workspace.update()
        for session in self._sessions:
            session.update_folders(workspace_folders)

    def enable_config_async(self, config_name: str) -> None:
        enable_in_project(self._window, config_name)
        self._configs.update()
        for listener in self._listeners:
            self.register_listener(listener)
        self._listeners.clear()
        if not self._new_session:
            sublime.set_timeout_async(self._dequeue_listener_async)

    def disable_config_async(self, config_name: str) -> None:
        disable_in_project(self._window, config_name)
        self._configs.update()
        self.end_config_sessions_async(config_name)

    def register_listener(self, listener: AbstractViewListener) -> None:
        sublime.set_timeout_async(lambda: self.register_listener_async(listener))

    def register_listener_async(self, listener: AbstractViewListener) -> None:
        if not self._workspace.contains(listener.view):
            # TODO: Handle views outside the workspace https://github.com/sublimelsp/LSP/issues/997
            return
        self._pending_listeners.appendleft(listener)
        if self._new_listener is None:
            self._dequeue_listener_async()

    def listeners(self) -> Generator[AbstractViewListener, None, None]:
        yield from self._listeners

    def listener_for_view(self, view: sublime.View) -> Optional[AbstractViewListener]:
        for listener in self.listeners():
            if listener.view == view:
                return listener
        return None

    def _dequeue_listener_async(self) -> None:
        listener = None  # type: Optional[AbstractViewListener]
        if self._new_listener is not None:
            listener = self._new_listener
            # debug("re-checking listener", listener)
            self._new_listener = None
        else:
            try:
                listener = self._pending_listeners.pop()
                if not listener.view.is_valid():
                    # debug("listener", listener, "is no longer valid")
                    return self._dequeue_listener_async()
                # debug("adding new pending listener", listener)
                self._listeners.add(listener)
            except IndexError:
                # We have handled all pending listeners.
                self._new_session = None
                return
        if self._new_session:
            self._sessions.add(self._new_session)
        self._publish_sessions_to_listener_async(listener)
        if self._new_session:
            if not any(self._new_session.session_views_async()):
                self._sessions.discard(self._new_session)
                self._new_session.end_async()
            self._new_session = None
        config = self._needed_config(listener.view)
        if config:
            # debug("found new config for listener", listener)
            self._new_listener = listener
            self.start_async(config, listener.view)
        else:
            # debug("no new config found for listener", listener)
            self._new_listener = None
            return self._dequeue_listener_async()

    def _publish_sessions_to_listener_async(self, listener: AbstractViewListener) -> None:
        # TODO: Handle views outside the workspace https://github.com/sublimelsp/LSP/issues/997
        if self._workspace.contains(listener.view):
            for session in self._sessions:
                if session.can_handle(listener.view):
                    # debug("registering session", session.config.name, "to listener", listener)
                    listener.on_session_initialized_async(session)

    def window(self) -> sublime.Window:
        return self._window

    def sessions(self, view: sublime.View, capability: Optional[str] = None) -> Generator[Session, None, None]:
        # TODO: Handle views outside the workspace https://github.com/sublimelsp/LSP/issues/997
        if self._workspace.contains(view):
            sessions = list(self._sessions)
            for session in sessions:
                if session.can_handle(view, capability):
                    yield session

    def get_session(self, config_name: str, file_path: str) -> Optional[Session]:
        return self._find_session(config_name, file_path)

    def _can_start_config(self, config_name: str, file_path: str) -> bool:
        return not bool(self._find_session(config_name, file_path))

    def _find_session(self, config_name: str, file_path: str) -> Optional[Session]:
        for session in self._sessions:
            if session.config.name == config_name and session.handles_path(file_path):
                return session
        return None

    def _needed_config(self, view: sublime.View) -> Optional[ClientConfig]:
        configs = self._configs.match_view(view)
        handled = False
        file_name = view.file_name() or ''
        if self._workspace.contains(view):
            for config in configs:
                handled = False
                for session in self._sessions:
                    if config.name == session.config.name and session.handles_path(file_name):
                        handled = True
                        break
                if not handled:
                    return config
        return None

    def start_async(self, config: ClientConfig, initiating_view: sublime.View) -> None:
        file_path = initiating_view.file_name() or ''
        if not self._can_start_config(config.name, file_path):
            # debug('Already starting on this window:', config.name)
            return
        try:
            workspace_folders = sorted_workspace_folders(self._workspace.folders, file_path)
            plugin_class = get_plugin(config.name)
            if plugin_class is not None:
                if plugin_class.needs_update_or_installation():
                    config.set_view_status(initiating_view, "installing...")
                    plugin_class.install_or_update()
                cannot_start_reason = plugin_class.can_start(
                    self._window, initiating_view, workspace_folders, config)
                if cannot_start_reason:
                    config.erase_view_status(initiating_view)
                    self._window.status_message(cannot_start_reason)
                    return
            config.set_view_status(initiating_view, "starting...")
            session = Session(self, self._create_logger(config.name), workspace_folders, config, plugin_class)
            cwd = workspace_folders[0].path if workspace_folders else None
            variables = extract_variables(self._window)
            if plugin_class is not None:
                additional_variables = plugin_class.additional_variables()
                if isinstance(additional_variables, dict):
                    variables.update(additional_variables)
            transport = create_transport(config, cwd, self._window, session, variables)
            config.set_view_status(initiating_view, "initialize")
            session.initialize(variables, transport)
            self._new_session = session
        except Exception as e:
            message = "\n\n".join([
                "Could not start {}",
                "{}",
                "Server will be disabled for this window"
            ]).format(config.name, str(e))
            exception_log("Unable to start {}".format(config.name), e)
            self._configs.disable_temporarily(config.name)
            config.erase_view_status(initiating_view)
            sublime.message_dialog(message)
            # Continue with handling pending listeners
            self._new_session = None
            sublime.set_timeout_async(self._dequeue_listener_async)

    def _create_logger(self, config_name: str) -> Logger:
        logger_map = {
            "panel": PanelLogger,
            "remote": RemoteLogger,
        }
        loggers = []
        for logger_type in settings.log_server:
            if logger_type not in logger_map:
                debug("Invalid logger type ({}) specified for log_server settings".format(logger_type))
                continue
            loggers.append(logger_map[logger_type])
        if len(loggers) == 0:
            return RouterLogger()  # logs nothing
        elif len(loggers) == 1:
            return loggers[0](self, config_name)
        else:
            router_logger = RouterLogger()
            for logger in loggers:
                router_logger.append(logger(self, config_name))
            return router_logger

    def handle_message_request(self, session: Session, params: Any, request_id: Any) -> None:
        view = self._window.active_view()
        if view:
            MessageRequestHandler(view, session, request_id, params, session.config.name).show()

    def restart_sessions_async(self) -> None:
        self.end_sessions_async()
        for listener in self._listeners:
            self.register_listener_async(listener)

    def end_sessions_async(self) -> None:
        for session in self._sessions:
            session.end_async()
        self._sessions.clear()

    def end_config_sessions_async(self, config_name: str) -> None:
        sessions = list(self._sessions)
        for session in sessions:
            if session.config.name == config_name:
                session.end_async()
                self._sessions.discard(session)

    def get_project_path(self, file_path: str) -> Optional[str]:
        candidate = None  # type: Optional[str]
        for folder in self._workspace.folders:
            if file_path.startswith(folder):
                if candidate is None or len(folder) > len(candidate):
                    candidate = folder
        return candidate

    def on_post_initialize(self, session: Session) -> None:
        sublime.set_timeout_async(self._dequeue_listener_async)

    def on_post_exit_async(self, session: Session, exit_code: int, exception: Optional[Exception]) -> None:
        self._sessions.discard(session)
        for view in self._window.views():
            file_name = view.file_name()
            if file_name:
                self.diagnostics.remove(file_name, session.config.name)
        for listener in self._listeners:
            listener.on_session_shutdown_async(session)
        if exit_code != 0:
            self._window.status_message("{} exited with status code {}".format(session.config.name, exit_code))
            fmt = "{0} exited with status code {1}.\n\nDo you want to restart {0}?\n\nIf you choose Cancel, {0} will "\
                  "be disabled for this window until you restart Sublime Text."
            msg = fmt.format(session.config.name, exit_code)
            if sublime.ok_cancel_dialog(msg, "Restart {}".format(session.config.name)):
                v = self._window.active_view()
                if not v:
                    return
                self.start_async(session.config, v)
            else:
                self._configs.disable_temporarily(session.config.name)
        if exception:
            self._window.status_message("{} exited with an exception: {}".format(session.config.name, exception))

    def handle_server_message(self, server_name: str, message: str) -> None:
        sublime.set_timeout(lambda: update_server_panel(self._window, server_name, message))

    def handle_log_message(self, session: Session, params: Any) -> None:
        self.handle_server_message(session.config.name, extract_message(params))

    def handle_stderr_log(self, session: Session, message: str) -> None:
        if self._settings.log_stderr:
            self.handle_server_message(session.config.name, message)

    def handle_show_message(self, session: Session, params: Any) -> None:
        sublime.status_message("{}: {}".format(session.config.name, extract_message(params)))


class WindowRegistry(object):
    def __init__(self, configs: ConfigManager) -> None:
        self._windows = {}  # type: Dict[int, WindowManager]
        self._configs = configs
        self._diagnostics_ui_class = None  # type: Optional[Callable]
        self._settings = None  # type: Optional[Settings]

    def set_diagnostics_ui(self, ui_class: Any) -> None:
        self._diagnostics_ui_class = ui_class

    def set_settings_factory(self, settings: Settings) -> None:
        self._settings = settings

    def lookup(self, window: sublime.Window) -> WindowManager:
        if not self._settings:
            raise RuntimeError("no settings")
        if window.id() in self._windows:
            return self._windows[window.id()]
        workspace = ProjectFolders(window)
        window_configs = self._configs.for_window(window)
        diagnostics_ui = self._diagnostics_ui_class(window) if self._diagnostics_ui_class else None
        state = WindowManager(
            window=window,
            workspace=workspace,
            settings=self._settings,
            configs=window_configs,
            diagnostics=DiagnosticsStorage(diagnostics_ui))
        self._windows[window.id()] = state
        return state

    def discard(self, window: sublime.Window) -> None:
        self._windows.pop(window.id(), None)


class PanelLogger(Logger):

    def __init__(self, manager: WindowManager, server_name: str) -> None:
        self._manager = ref(manager)
        self._server_name = server_name

    def stderr_message(self, message: str) -> None:
        """
        Not handled here as stderr messages are handled by WindowManager regardless
        if this logger is enabled.
        """
        pass

    def log(self, message: str, params: Any) -> None:

        def run_on_async_worker_thread() -> None:
            nonlocal message
            params_str = str(params)
            if len(params_str) >= settings.log_max_size:
                params_str = '<params with {} characters>'.format(len(params_str))
            message = "{}: {}".format(message, params_str)
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

    def outgoing_request(self, request_id: int, method: str, params: Any) -> None:
        if not settings.log_server:
            return
        self.log(self._format_request("-->", method, request_id), params)

    def outgoing_notification(self, method: str, params: Any) -> None:
        if not settings.log_server:
            return
        self.log(self._format_notification(" ->", method), params)

    def incoming_response(self, request_id: int, params: Any, is_error: bool) -> None:
        if not settings.log_server:
            return
        direction = "<~~" if is_error else "<<<"
        self.log(self._format_response(direction, request_id), params)

    def incoming_request(self, request_id: Any, method: str, params: Any) -> None:
        if not settings.log_server:
            return
        self.log(self._format_request("<--", method, request_id), params)

    def incoming_notification(self, method: str, params: Any, unhandled: bool) -> None:
        if not settings.log_server:
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
        self._server_name = server_name
        if not RemoteLogger._ws_server:
            try:
                RemoteLogger._ws_server = WebsocketServer(self.PORT)
                RemoteLogger._ws_server.set_fn_new_client(self._on_new_client)
                RemoteLogger._ws_server.set_fn_client_left(self._on_client_left)
                RemoteLogger._ws_server.set_fn_message_received(self._on_message_received)
                self._start_server()
            except OSError as ex:
                if ex.errno == 48:  # Address already in use
                    debug('WebsocketServer not started - address already in use')
                    RemoteLogger._ws_server = None
                else:
                    raise ex

    def _start_server(self) -> None:
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

    def stderr_message(self, message: str) -> None:
        self._broadcast_json({
            'server': self._server_name,
            'time': round(time() * 1000),
            'method': 'stderr',
            'params': message,
            'isError': True,
            'direction': self.DIRECTION_INCOMING,
        })

    def outgoing_request(self, request_id: int, method: str, params: Any) -> None:
        self._broadcast_json({
            'server': self._server_name,
            'id': request_id,
            'time': round(time() * 1000),
            'method': method,
            'params': params,
            'direction': self.DIRECTION_OUTGOING,
        })

    def incoming_response(self, request_id: int, params: Any, is_error: bool) -> None:
        self._broadcast_json({
            'server': self._server_name,
            'id': request_id,
            'time': round(time() * 1000),
            'params': params,
            'direction': self.DIRECTION_INCOMING,
            'isError': is_error,
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


class RouterLogger(Logger):
    def __init__(self) -> None:
        self._loggers = []  # type: List[Logger]

    def append(self, logger: Logger) -> None:
        self._loggers.append(logger)

    def stderr_message(self, *args: Any, **kwargs: Any) -> None:
        self._foreach("stderr_message", *args, **kwargs)

    def outgoing_response(self, *args: Any, **kwargs: Any) -> None:
        self._foreach("outgoing_response", *args, **kwargs)

    def outgoing_error_response(self, *args: Any, **kwargs: Any) -> None:
        self._foreach("outgoing_error_response", *args, **kwargs)

    def outgoing_request(self, *args: Any, **kwargs: Any) -> None:
        self._foreach("outgoing_request", *args, **kwargs)

    def outgoing_notification(self, *args: Any, **kwargs: Any) -> None:
        self._foreach("outgoing_notification", *args, **kwargs)

    def incoming_response(self, *args: Any, **kwargs: Any) -> None:
        self._foreach("incoming_response", *args, **kwargs)

    def incoming_request(self, *args: Any, **kwargs: Any) -> None:
        self._foreach("incoming_request", *args, **kwargs)

    def incoming_notification(self, *args: Any, **kwargs: Any) -> None:
        self._foreach("incoming_notification", *args, **kwargs)

    def _foreach(self, method: str, *args: Any, **kwargs: Any) -> None:
        for logger in self._loggers:
            getattr(logger, method)(*args, **kwargs)
