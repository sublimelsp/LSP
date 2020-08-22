from ...third_party import WebsocketServer  # type: ignore
from .configurations import ConfigManager
from .configurations import WindowConfigManager
from .diagnostics import DiagnosticsCursor
from .diagnostics import DiagnosticsWalker
from .diagnostics import ensure_diagnostics_panel
from .logging import debug
from .logging import exception_log
from .message_request_handler import MessageRequestHandler
from .panels import update_server_panel
from .protocol import Diagnostic
from .protocol import Error
from .protocol import Point
from .rpc import Logger
from .sessions import get_plugin
from .sessions import Manager
from .sessions import Session
from .settings import userprefs
from .transports import create_transport
from .types import ClientConfig
from .typing import Optional, Any, Dict, Deque, List, Generator, Tuple, Mapping, Iterable
from .views import diagnostic_to_phantom
from .views import extract_variables
from .workspace import disable_in_project
from .workspace import enable_in_project
from .workspace import ProjectFolders
from .workspace import sorted_workspace_folders
from abc import ABCMeta
from abc import abstractmethod
from collections import deque
from copy import deepcopy
from subprocess import CalledProcessError
from time import time
from weakref import ref
from weakref import WeakSet
import json
import os
import sublime
import threading


class AbstractViewListener(metaclass=ABCMeta):

    TOTAL_ERRORS_AND_WARNINGS_STATUS_KEY = "lsp_total_errors_and_warnings"

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

    @abstractmethod
    def diagnostics_async(self) -> Dict[str, List[Diagnostic]]:
        raise NotImplementedError()

    @abstractmethod
    def diagnostics_panel_contribution_async(self) -> List[str]:
        raise NotImplementedError()

    @abstractmethod
    def sum_total_errors_and_warnings_async(self) -> Tuple[int, int]:
        raise NotImplementedError()

    @abstractmethod
    def update_diagnostic_in_status_bar_async(self) -> None:
        raise NotImplementedError()


def extract_message(params: Any) -> str:
    return params.get("message", "???") if isinstance(params, dict) else "???"


def set_diagnostics_count(view: sublime.View, errors: int, warnings: int) -> None:
    try:
        key = AbstractViewListener.TOTAL_ERRORS_AND_WARNINGS_STATUS_KEY
        if userprefs().show_diagnostics_count_in_view_status:
            view.set_status(key, "E: {}, W: {}".format(errors, warnings))
        else:
            view.erase_status(key)
    except Exception:
        pass


class WindowManager(Manager):

    DIAGNOSTIC_PHANTOM_KEY = "lsp_diagnostic_phantom"

    def __init__(
        self,
        window: sublime.Window,
        workspace: ProjectFolders,
        configs: WindowConfigManager,
    ) -> None:
        self._window = window
        self._configs = configs
        self._sessions = WeakSet()  # type: WeakSet[Session]
        self._workspace = workspace
        self._pending_listeners = deque()  # type: Deque[AbstractViewListener]
        self._listeners = WeakSet()  # type: WeakSet[AbstractViewListener]
        self._new_listener = None  # type: Optional[AbstractViewListener]
        self._new_session = None  # type: Optional[Session]
        self._cursor = DiagnosticsCursor(userprefs().show_diagnostics_severity_level)
        self._diagnostic_phantom_set = None  # type: Optional[sublime.PhantomSet]
        self.total_error_count = 0
        self.total_warning_count = 0

    def get_config_manager(self) -> WindowConfigManager:
        return self._configs

    def on_load_project_async(self) -> None:
        self._workspace.update()
        self._configs.update()

    def enable_config_async(self, config_name: str) -> None:
        enable_in_project(self._window, config_name)
        # TODO: Why doesn't enable_in_project cause on_load_project_async to be called?
        self._configs.update()

    def disable_config_async(self, config_name: str) -> None:
        disable_in_project(self._window, config_name)
        # TODO: Why doesn't disable_in_project cause on_load_project_async to be called?
        self._configs.update()

    def _register_listener(self, listener: AbstractViewListener) -> None:
        sublime.set_timeout_async(lambda: self.register_listener_async(listener))

    def register_listener_async(self, listener: AbstractViewListener) -> None:
        set_diagnostics_count(listener.view, self.total_error_count, self.total_warning_count)
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
            session.initialize(
                variables, transport,
                lambda session, is_error: self._on_post_session_initialize(initiating_view, session, is_error))
            self._new_session = session
        except Exception as e:
            message = "\n\n".join([
                "Could not start {}",
                "{}",
                "Server will be disabled for this window"
            ]).format(config.name, str(e))
            exception_log("Unable to start {}".format(config.name), e)
            if isinstance(e, CalledProcessError):
                print("Server output:\n{}".format(e.output.decode('utf-8', 'replace')))
            self._configs.disable_temporarily(config.name)
            config.erase_view_status(initiating_view)
            sublime.message_dialog(message)
            # Continue with handling pending listeners
            self._new_session = None
            sublime.set_timeout_async(self._dequeue_listener_async)

    def _on_post_session_initialize(
        self, initiating_view: sublime.View, session: Session, is_error: bool = False
    ) -> None:
        if is_error:
            session.config.erase_view_status(initiating_view)
            self._new_listener = None
            self._new_session = None
        else:
            sublime.set_timeout_async(self._dequeue_listener_async)

    def _create_logger(self, config_name: str) -> Logger:
        logger_map = {
            "panel": PanelLogger,
            "remote": RemoteLogger,
        }
        loggers = []
        for logger_type in userprefs().log_server:
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
        listeners = list(self._listeners)
        self._listeners.clear()
        for listener in listeners:
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

    def on_post_exit_async(self, session: Session, exit_code: int, exception: Optional[Exception]) -> None:
        self._sessions.discard(session)
        for listener in self._listeners:
            listener.on_session_shutdown_async(session)
        if exit_code != 0 or exception:
            config = session.config
            msg = "{} exited with status code {}".format(config.name, exit_code)
            if exception:
                msg += " and message:\n\n---\n{}\n---".format(str(exception))
            msg += "\n\nDo you want to restart {0}?\n\nIf you choose Cancel, {0} will "\
                   "be disabled for this window until you restart Sublime Text.".format(config.name)
            if sublime.ok_cancel_dialog(msg, "Restart {}".format(config.name)):
                view = self._window.active_view()
                if view:
                    self.start_async(config, view)
            else:
                self._configs.disable_temporarily(config.name)

    def handle_server_message(self, server_name: str, message: str) -> None:
        sublime.set_timeout(lambda: update_server_panel(self._window, server_name, message))

    def handle_log_message(self, session: Session, params: Any) -> None:
        self.handle_server_message(session.config.name, extract_message(params))

    def handle_stderr_log(self, session: Session, message: str) -> None:
        if userprefs().log_stderr:
            self.handle_server_message(session.config.name, message)

    def handle_show_message(self, session: Session, params: Any) -> None:
        sublime.status_message("{}: {}".format(session.config.name, extract_message(params)))

    def update_diagnostics_panel_async(self) -> None:
        panel = ensure_diagnostics_panel(self._window)
        if not panel:
            return
        to_render = []  # type: List[str]
        base_dir = None
        self.total_error_count = 0
        self.total_warning_count = 0
        listeners = list(self._listeners)
        for listener in listeners:
            local_errors, local_warnings = listener.sum_total_errors_and_warnings_async()
            self.total_error_count += local_errors
            self.total_warning_count += local_warnings
            contribution = listener.diagnostics_panel_contribution_async()
            if not contribution:
                continue
            file_path = listener.view.file_name() or ""
            base_dir = self.get_project_path(file_path)  # What about different base dirs for multiple folders?
            file_path = os.path.relpath(file_path, base_dir) if base_dir else file_path
            to_render.append(" ◌ {}:".format(file_path))
            to_render.extend(contribution)
        if isinstance(base_dir, str):
            panel.settings().set("result_base_dir", base_dir)
        else:
            panel.settings().erase("result_base_dir")
        panel.run_command("lsp_update_panel", {"characters": "\n".join(to_render)})
        for listener in listeners:
            set_diagnostics_count(listener.view, self.total_error_count, self.total_warning_count)

    def _can_manipulate_diagnostics_panel(self) -> bool:
        active_panel = self._window.active_panel()
        if active_panel is not None:
            return active_panel == "output.diagnostics"
        return True

    def show_diagnostics_panel_async(self) -> None:
        if self._can_manipulate_diagnostics_panel():
            self._window.run_command("show_panel", {"panel": "output.diagnostics"})

    def hide_diagnostics_panel_async(self) -> None:
        if self._can_manipulate_diagnostics_panel():
            self._window.run_command("hide_panel", {"panel": "output.diagnostics"})

    def select_next_diagnostic_async(self) -> None:
        self._select_diagnostic_async(1)

    def select_previous_diagnostic_async(self) -> None:
        self._select_diagnostic_async(-1)

    def unselect_diagnostic_async(self) -> None:
        self._set_diagnostic_phantom(None)

    def _diagnostics_by_file_async(self) -> Generator[Tuple[str, Mapping[str, Iterable[Diagnostic]]], None, None]:
        for listener in self._listeners:
            file_name = listener.view.file_name()
            if file_name:
                yield file_name, listener.diagnostics_async()

    def _select_diagnostic_async(self, direction: int) -> None:
        file_path = None  # type: Optional[str]
        point = None  # type: Optional[Point]
        if not self._cursor.has_value:
            active_view = self._window.active_view()
            if active_view:
                file_path = active_view.file_name()
                point = Point(*active_view.rowcol(active_view.sel()[0].begin()))
        walk = self._cursor.from_diagnostic(direction) if self._cursor.has_value else self._cursor.from_position(
            direction, file_path, point)
        walker = DiagnosticsWalker([walk])
        walker.walk(self._diagnostics_by_file_async())
        # The actual presentation of the phantom needs to happen on the UI thread, otherwise you'll see a phantom
        # disappearing and then immediately after a phantom appearing. This is jarring. So run blocking.
        sublime.set_timeout(lambda: self._set_diagnostic_phantom(self._cursor.value))

    def _set_diagnostic_phantom(self, file_diagnostic: Optional[Tuple[str, Diagnostic]]) -> None:
        self._clear_diagnostic_phantom()
        if file_diagnostic:
            file_path, diagnostic = file_diagnostic
            view = self._window.find_open_file(file_path)
            if view:
                phantom_set = sublime.PhantomSet(view, self.DIAGNOSTIC_PHANTOM_KEY)
                base_dir = self.get_project_path(file_path)
                phantom = diagnostic_to_phantom(view, diagnostic, base_dir, self._navigate_diagnostic_phantom)
                phantom_set.update([phantom])
                self._window.focus_view(view)
                view.show_at_center(phantom.region)
                self._diagnostic_phantom_set = phantom_set
                has_phantom = view.settings().get(self.DIAGNOSTIC_PHANTOM_KEY)
                if not has_phantom:
                    view.settings().set(self.DIAGNOSTIC_PHANTOM_KEY, True)
            else:
                debug("no view for file", file_path)
        else:
            if self._diagnostic_phantom_set:
                view = self._diagnostic_phantom_set.view
                has_phantom = view.settings().get(self.DIAGNOSTIC_PHANTOM_KEY)
                if not has_phantom:
                    view.settings().set(self.DIAGNOSTIC_PHANTOM_KEY, False)

    def _navigate_diagnostic_phantom(self, href: str) -> None:
        if href == "hide":
            self._clear_diagnostic_phantom()
        elif href == "next":
            self._window.run_command("lsp_next_diagnostic")
        elif href == "previous":
            self._window.run_command("lsp_previous_diagnostic")
        elif href.startswith("location"):
            # todo: share with hover?
            _, file_path, location = href.split(":", 2)
            self._window.open_file(file_path + ":" + location, sublime.ENCODED_POSITION | sublime.TRANSIENT)

    def _clear_diagnostic_phantom(self) -> None:
        if self._diagnostic_phantom_set:
            self._diagnostic_phantom_set.view.settings().set(self.DIAGNOSTIC_PHANTOM_KEY, False)
            self._diagnostic_phantom_set.update([])


class WindowRegistry(object):
    def __init__(self, configs: ConfigManager) -> None:
        self._windows = {}  # type: Dict[int, WindowManager]
        self._configs = configs

    def lookup(self, window: sublime.Window) -> WindowManager:
        if window.id() in self._windows:
            return self._windows[window.id()]
        workspace = ProjectFolders(window)
        window_configs = self._configs.for_window(window)
        state = WindowManager(window=window, workspace=workspace, configs=window_configs)
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
            if 0 < userprefs().log_max_size <= len(params_str):
                params_str = '<params with {} characters>'.format(len(params_str))
            message = "{}: {}".format(message, params_str)
            manager = self._manager()
            if manager is not None:
                manager.handle_server_message(":", message)

        sublime.set_timeout_async(run_on_async_worker_thread)

    def outgoing_response(self, request_id: Any, params: Any) -> None:
        if not userprefs().log_server:
            return
        self.log(self._format_response(">>>", request_id), params)

    def outgoing_error_response(self, request_id: Any, error: Error) -> None:
        if not userprefs().log_server:
            return
        self.log(self._format_response("~~>", request_id), error.to_lsp())

    def outgoing_request(self, request_id: int, method: str, params: Any) -> None:
        if not userprefs().log_server:
            return
        self.log(self._format_request("-->", method, request_id), params)

    def outgoing_notification(self, method: str, params: Any) -> None:
        if not userprefs().log_server:
            return
        self.log(self._format_notification(" ->", method), params)

    def incoming_response(self, request_id: int, params: Any, is_error: bool) -> None:
        if not userprefs().log_server:
            return
        direction = "<~~" if is_error else "<<<"
        self.log(self._format_response(direction, request_id), params)

    def incoming_request(self, request_id: Any, method: str, params: Any) -> None:
        if not userprefs().log_server:
            return
        self.log(self._format_request("<--", method, request_id), params)

    def incoming_notification(self, method: str, params: Any, unhandled: bool) -> None:
        if not userprefs().log_server:
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
    _last_id = 0

    def __init__(self, manager: WindowManager, server_name: str) -> None:
        RemoteLogger._last_id += 1
        self._server_name = '{} ({})'.format(server_name, RemoteLogger._last_id)
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
