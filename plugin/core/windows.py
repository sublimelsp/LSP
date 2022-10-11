from ...third_party import WebsocketServer  # type: ignore
from .configurations import ConfigManager
from .configurations import WindowConfigManager
from .diagnostics import ensure_diagnostics_panel
from .diagnostics_storage import is_severity_included
from .logging import debug
from .logging import exception_log
from .message_request_handler import MessageRequestHandler
from .panels import destroy_output_panels
from .panels import ensure_log_panel
from .panels import is_panel_open
from .panels import log_server_message
from .panels import PanelName
from .promise import Promise
from .protocol import DocumentUri
from .protocol import Error
from .protocol import Location
from .protocol import LocationLink
from .sessions import AbstractViewListener
from .sessions import get_plugin
from .sessions import Logger
from .sessions import Manager
from .sessions import Session
from .settings import userprefs
from .transports import create_transport
from .types import ClientConfig
from .types import matches_pattern
from .typing import Optional, Any, Dict, Deque, List, Generator, Tuple, Union
from .url import parse_uri
from .views import extract_variables
from .views import format_diagnostic_for_panel
from .views import make_link
from .workspace import ProjectFolders
from .workspace import sorted_workspace_folders
from collections import deque
from collections import OrderedDict
from subprocess import CalledProcessError
from time import time
from weakref import ref
from weakref import WeakSet
import functools
import json
import sublime
import threading
import urllib.parse


_NO_DIAGNOSTICS_PLACEHOLDER = "  No diagnostics. Well done!"


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
        self._panel_code_phantoms = None  # type: Optional[sublime.PhantomSet]
        self.total_error_count = 0
        self.total_warning_count = 0
        sublime.set_timeout(functools.partial(self._update_panel_main_thread, _NO_DIAGNOSTICS_PLACEHOLDER, []))
        ensure_log_panel(window)

    @property
    def window(self) -> sublime.Window:
        return self._window

    def get_config_manager(self) -> WindowConfigManager:
        return self._configs

    def get_sessions(self) -> Generator[Session, None, None]:
        yield from self._sessions

    def on_load_project_async(self) -> None:
        self.update_workspace_folders_async()
        self._configs.update()

    def on_post_save_project_async(self) -> None:
        self.on_load_project_async()

    def update_workspace_folders_async(self) -> None:
        if self._workspace.update():
            workspace_folders = self._workspace.get_workspace_folders()
            for session in self._sessions:
                session.update_folders(workspace_folders)

    def enable_config_async(self, config_name: str) -> None:
        self._configs.enable_config(config_name)

    def disable_config_async(self, config_name: str) -> None:
        self._configs.disable_config(config_name)

    def open_location_async(
        self,
        location: Union[Location, LocationLink],
        session_name: Optional[str],
        view: sublime.View,
        flags: int = 0,
        group: int = -1
    ) -> Promise[Optional[sublime.View]]:
        for session in self.sessions(view):
            if session_name is None or session_name == session.config.name:
                return session.open_location_async(location, flags, group)
        return Promise.resolve(None)

    def register_listener_async(self, listener: AbstractViewListener) -> None:
        set_diagnostics_count(listener.view, self.total_error_count, self.total_warning_count)
        # Update workspace folders in case the user have changed those since window was created.
        # There is no currently no notification in ST that would notify about folder changes.
        self.update_workspace_folders_async()
        self._pending_listeners.appendleft(listener)
        if self._new_listener is None:
            self._dequeue_listener_async()

    def unregister_listener_async(self, listener: AbstractViewListener) -> None:
        self._listeners.discard(listener)

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
            self._dequeue_listener_async()

    def _publish_sessions_to_listener_async(self, listener: AbstractViewListener) -> None:
        inside_workspace = self._workspace.contains(listener.view)
        scheme = urllib.parse.urlparse(listener.get_uri()).scheme
        for session in self._sessions:
            if session.can_handle(listener.view, scheme, capability=None, inside_workspace=inside_workspace):
                # debug("registering session", session.config.name, "to listener", listener)
                try:
                    listener.on_session_initialized_async(session)
                except Exception as ex:
                    message = "failed to register session {} to listener {}".format(session.config.name, listener)
                    exception_log(message, ex)

    def sessions(self, view: sublime.View, capability: Optional[str] = None) -> Generator[Session, None, None]:
        inside_workspace = self._workspace.contains(view)
        sessions = list(self._sessions)
        uri = view.settings().get("lsp_uri")
        if not isinstance(uri, str):
            return
        scheme = urllib.parse.urlparse(uri).scheme
        for session in sessions:
            if session.can_handle(view, scheme, capability, inside_workspace):
                yield session

    def get_session(self, config_name: str, file_path: str) -> Optional[Session]:
        return self._find_session(config_name, file_path)

    def _can_start_config(self, config_name: str, file_path: str) -> bool:
        return not bool(self._find_session(config_name, file_path))

    def _find_session(self, config_name: str, file_path: str) -> Optional[Session]:
        inside = self._workspace.contains(file_path)
        for session in self._sessions:
            if session.config.name == config_name and session.handles_path(file_path, inside):
                return session
        return None

    def _needed_config(self, view: sublime.View) -> Optional[ClientConfig]:
        configs = self._configs.match_view(view)
        handled = False
        file_name = view.file_name()
        inside = self._workspace.contains(view)
        for config in configs:
            handled = False
            for session in self._sessions:
                if config.name == session.config.name and session.handles_path(file_name, inside):
                    handled = True
                    break
            if not handled:
                return config
        return None

    def start_async(self, config: ClientConfig, initiating_view: sublime.View) -> None:
        config = ClientConfig.from_config(config, {})
        file_path = initiating_view.file_name() or ''
        if not self._can_start_config(config.name, file_path):
            # debug('Already starting on this window:', config.name)
            return
        try:
            workspace_folders = sorted_workspace_folders(self._workspace.folders, file_path)
            plugin_class = get_plugin(config.name)
            variables = extract_variables(self._window)
            cwd = None  # type: Optional[str]
            if plugin_class is not None:
                if plugin_class.needs_update_or_installation():
                    config.set_view_status(initiating_view, "installing...")
                    plugin_class.install_or_update()
                additional_variables = plugin_class.additional_variables()
                if isinstance(additional_variables, dict):
                    variables.update(additional_variables)
                cannot_start_reason = plugin_class.can_start(self._window, initiating_view, workspace_folders, config)
                if cannot_start_reason:
                    config.erase_view_status(initiating_view)
                    message = "cannot start {}: {}".format(config.name, cannot_start_reason)
                    self._configs.disable_config(config.name, only_for_session=True)
                    # Continue with handling pending listeners
                    self._new_session = None
                    sublime.set_timeout_async(self._dequeue_listener_async)
                    return self._window.status_message(message)
                cwd = plugin_class.on_pre_start(self._window, initiating_view, workspace_folders, config)
            config.set_view_status(initiating_view, "starting...")
            session = Session(self, self._create_logger(config.name), workspace_folders, config, plugin_class)
            if cwd:
                transport_cwd = cwd  # type: Optional[str]
            else:
                transport_cwd = workspace_folders[0].path if workspace_folders else None
            transport_config = config.resolve_transport_config(variables)
            transport = create_transport(transport_config, transport_cwd, session)
            if plugin_class:
                plugin_class.on_post_start(self._window, initiating_view, workspace_folders, config)
            config.set_view_status(initiating_view, "initialize")
            session.initialize_async(
                variables=variables,
                transport=transport,
                working_directory=cwd,
                init_callback=functools.partial(self._on_post_session_initialize, initiating_view)
            )
            self._new_session = session
        except Exception as e:
            message = "".join((
                "Failed to start {0} - disabling for this window for the duration of the current session.\n",
                "Re-enable by running \"LSP: Enable Language Server In Project\" from the Command Palette.",
                "\n\n--- Error: ---\n{1}"
            )).format(config.name, str(e))
            exception_log("Unable to start subprocess for {}".format(config.name), e)
            if isinstance(e, CalledProcessError):
                print("Server output:\n{}".format(e.output.decode('utf-8', 'replace')))
            self._configs.disable_config(config.name, only_for_session=True)
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

    def restart_sessions_async(self, config_name: Optional[str] = None) -> None:
        self._end_sessions_async(config_name)
        listeners = list(self._listeners)
        self._listeners.clear()
        for listener in listeners:
            self.register_listener_async(listener)

    def _end_sessions_async(self, config_name: Optional[str] = None) -> None:
        sessions = list(self._sessions)
        for session in sessions:
            if config_name is None or config_name == session.config.name:
                session.end_async()
                self._sessions.discard(session)

    def get_project_path(self, file_path: str) -> Optional[str]:
        candidate = None  # type: Optional[str]
        for folder in self._workspace.folders:
            if file_path.startswith(folder):
                if candidate is None or len(folder) > len(candidate):
                    candidate = folder
        return candidate

    def should_present_diagnostics(self, uri: DocumentUri) -> Optional[str]:
        scheme, path = parse_uri(uri)
        if scheme != "file":
            return None
        if not self._workspace.contains(path):
            return "not inside window folders"
        view = self._window.active_view()
        if not view:
            return None
        settings = view.settings()
        if matches_pattern(path, settings.get("binary_file_patterns")):
            return "matches a pattern in binary_file_patterns"
        if matches_pattern(path, settings.get("file_exclude_patterns")):
            return "matches a pattern in file_exclude_patterns"
        if matches_pattern(path, settings.get("folder_exclude_patterns")):
            return "matches a pattern in folder_exclude_patterns"
        return None

    def on_post_exit_async(self, session: Session, exit_code: int, exception: Optional[Exception]) -> None:
        self._sessions.discard(session)
        for listener in self._listeners:
            listener.on_session_shutdown_async(session)
        if exit_code != 0 or exception:
            config = session.config
            msg = "".join((
                "{0} exited with status code {1}. ",
                "Do you want to restart it? If you choose Cancel, it will be disabled for this window for the ",
                "duration of the current session. ",
                "Re-enable by running \"LSP: Enable Language Server In Project\" from the Command Palette."
            )).format(config.name, exit_code)
            if exception:
                msg += "\n\n--- Error: ---\n{}".format(str(exception))
            if sublime.ok_cancel_dialog(msg, "Restart {}".format(config.name)):
                for listener in self._listeners:
                    self.register_listener_async(listener)
            else:
                self._configs.disable_config(config.name, only_for_session=True)

    def plugin_unloaded(self) -> None:
        """
        This is called **from the main thread** when the plugin unloads. In that case we must destroy all sessions
        from the main thread. That could lead to some dict/list being mutated while iterated over, so be careful
        """
        self._end_sessions_async()

    def handle_server_message(self, server_name: str, message: str) -> None:
        sublime.set_timeout(lambda: log_server_message(self._window, server_name, message))

    def handle_log_message(self, session: Session, params: Any) -> None:
        self.handle_server_message(session.config.name, extract_message(params))

    def handle_stderr_log(self, session: Session, message: str) -> None:
        self.handle_server_message(session.config.name, message)

    def handle_show_message(self, session: Session, params: Any) -> None:
        sublime.status_message("{}: {}".format(session.config.name, extract_message(params)))

    def on_diagnostics_updated(self) -> None:
        self.total_error_count = 0
        self.total_warning_count = 0
        for session in self._sessions:
            local_errors, local_warnings = session.diagnostics.sum_total_errors_and_warnings_async()
            self.total_error_count += local_errors
            self.total_warning_count += local_warnings
        for listener in list(self._listeners):
            set_diagnostics_count(listener.view, self.total_error_count, self.total_warning_count)
        if is_panel_open(self._window, PanelName.Diagnostics):
            self.update_diagnostics_panel_async()

    def update_diagnostics_panel_async(self) -> None:
        to_render = []  # type: List[str]
        prephantoms = []  # type: List[Tuple[int, int, str, str]]
        row = 0
        max_severity = userprefs().diagnostics_panel_include_severity_level
        contributions = OrderedDict(
        )  # type: OrderedDict[str, List[Tuple[str, Optional[int], Optional[str], Optional[str]]]]
        for session in self._sessions:
            for (_, path), contribution in session.diagnostics.filter_map_diagnostics_async(
                    is_severity_included(max_severity), lambda _, diagnostic: format_diagnostic_for_panel(diagnostic)):
                seen = path in contributions
                contributions.setdefault(path, []).extend(contribution)
                if not seen:
                    contributions.move_to_end(path)
        for path, contribution in contributions.items():
            to_render.append("{}:".format(path))
            row += 1
            for content, offset, code, href in contribution:
                to_render.append(content)
                if offset is not None and code is not None and href is not None:
                    prephantoms.append((row, offset, code, href))
                row += content.count("\n") + 1
            to_render.append("")  # add spacing between filenames
            row += 1
        characters = "\n".join(to_render)
        if not characters:
            characters = _NO_DIAGNOSTICS_PLACEHOLDER
        sublime.set_timeout(functools.partial(self._update_panel_main_thread, characters, prephantoms))

    def _update_panel_main_thread(self, characters: str, prephantoms: List[Tuple[int, int, str, str]]) -> None:
        panel = ensure_diagnostics_panel(self._window)
        if not panel or not panel.is_valid():
            return
        panel.run_command("lsp_update_panel", {"characters": characters})
        if self._panel_code_phantoms is None:
            self._panel_code_phantoms = sublime.PhantomSet(panel, "hrefs")
        phantoms = []  # type: List[sublime.Phantom]
        for row, col, code, href in prephantoms:
            point = panel.text_point(row, col)
            region = sublime.Region(point, point)
            phantoms.append(sublime.Phantom(region, make_link(href, code), sublime.LAYOUT_INLINE))
        self._panel_code_phantoms.update(phantoms)

    def show_diagnostics_panel_async(self) -> None:
        if self._window.active_panel() is None:
            self._window.run_command("show_panel", {"panel": "output.diagnostics"})

    def hide_diagnostics_panel_async(self) -> None:
        if is_panel_open(self._window, PanelName.Diagnostics):
            self._window.run_command("hide_panel", {"panel": "output.diagnostics"})


class WindowRegistry(object):
    def __init__(self, configs: ConfigManager) -> None:
        self._enabled = False
        self._windows = {}  # type: Dict[int, WindowManager]
        self._configs = configs

    def enable(self) -> None:
        self._enabled = True
        # Initialize manually at plugin_loaded as we'll miss out on "on_new_window_async" events.
        for window in sublime.windows():
            self.lookup(window)

    def disable(self) -> None:
        self._enabled = False
        for manager in self._windows.values():
            try:
                manager.plugin_unloaded()
            except Exception as ex:
                exception_log("failed to unload window", ex)
        for manager in self._windows.values():
            destroy_output_panels(manager.window)
        self._windows = {}

    def lookup(self, window: Optional[sublime.Window]) -> Optional[WindowManager]:
        if not self._enabled or not window or not window.is_valid():
            return None
        self.clear_invalid_windows_workaround()
        wm = self._windows.get(window.id())
        if wm:
            return wm
        workspace = ProjectFolders(window)
        window_configs = self._configs.for_window(window)
        manager = WindowManager(window, workspace, window_configs)
        self._windows[window.id()] = manager
        return manager

    def listener_for_view(self, view: sublime.View) -> Optional[AbstractViewListener]:
        manager = self.lookup(view.window())
        if not manager:
            return None
        return manager.listener_for_view(view)

    def discard(self, window: sublime.Window) -> None:
        self._windows.pop(window.id(), None)
        self.clear_invalid_windows_workaround()

    def clear_invalid_windows_workaround(self) -> None:
        # Due to "on_pre_close_window" not working currently (https://github.com/sublimehq/sublime_text/issues/5148)
        # we'll check for invalid (closed) Windows and remove them from the list.
        for key in list(self._windows.keys()):
            window = self._windows[key].window
            if not window.is_valid():
                self.discard(window)


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
            params_str = repr(params)
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
        self._broadcast_json({
            'server': self._server_name,
            'time': round(time() * 1000),
            'method': method,
            'params': params,
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
