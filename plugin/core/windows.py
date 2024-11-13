from __future__ import annotations
from ...third_party import WebsocketServer  # type: ignore
from .configurations import RETRY_COUNT_TIMEDELTA
from .configurations import RETRY_MAX_COUNT
from .configurations import WindowConfigChangeListener
from .configurations import WindowConfigManager
from .diagnostics_storage import is_severity_included
from .logging import debug
from .logging import exception_log
from .message_request_handler import MessageRequestHandler
from .panels import LOG_LINES_LIMIT_SETTING_NAME
from .panels import MAX_LOG_LINES_LIMIT_OFF
from .panels import MAX_LOG_LINES_LIMIT_ON
from .panels import PanelManager
from .panels import PanelName
from .protocol import DocumentUri
from .protocol import Error
from .protocol import LogMessageParams
from .protocol import MessageType
from .sessions import AbstractViewListener
from .sessions import get_plugin
from .sessions import Logger
from .sessions import Manager
from .sessions import Session
from .settings import client_configs
from .settings import LspSettingsChangeListener
from .settings import userprefs
from .transports import create_transport
from .types import ClientConfig
from .types import matches_pattern
from .types import sublime_pattern_to_glob
from .url import parse_uri
from .views import extract_variables
from .views import format_diagnostic_for_panel
from .views import make_link
from .workspace import ProjectFolders
from .workspace import sorted_workspace_folders
from collections import deque
from collections import OrderedDict
from datetime import datetime
from subprocess import CalledProcessError
from time import perf_counter
from typing import Any, Generator, TYPE_CHECKING
from weakref import ref
from weakref import WeakSet
import functools
import json
import sublime
import threading


if TYPE_CHECKING:
    from tree_view import TreeViewSheet


_NO_DIAGNOSTICS_PLACEHOLDER = "  No diagnostics. Well done!"


def extract_message(params: Any) -> str:
    return params.get("message", "???") if isinstance(params, dict) else "???"


def set_diagnostics_count(view: sublime.View, errors: int, warnings: int) -> None:
    try:
        key = AbstractViewListener.TOTAL_ERRORS_AND_WARNINGS_STATUS_KEY
        if userprefs().show_diagnostics_count_in_view_status:
            view.set_status(key, f"E: {errors}, W: {warnings}")
        else:
            view.erase_status(key)
    except Exception:
        pass


class WindowManager(Manager, WindowConfigChangeListener):

    def __init__(self, window: sublime.Window, workspace: ProjectFolders, config_manager: WindowConfigManager) -> None:
        self._window = window
        self._config_manager = config_manager
        self._sessions: set[Session] = set()
        self._workspace = workspace
        self._pending_listeners: deque[AbstractViewListener] = deque()
        self._listeners: WeakSet[AbstractViewListener] = WeakSet()
        self._new_listener: AbstractViewListener | None = None
        self._new_session: Session | None = None
        self._panel_code_phantoms: sublime.PhantomSet | None = None
        self._server_log: list[tuple[str, str]] = []
        self.panel_manager: PanelManager | None = PanelManager(self._window)
        self.tree_view_sheets: dict[str, TreeViewSheet] = {}
        self.formatters: dict[str, str] = {}
        self.suppress_sessions_restart_on_project_update = False
        self.total_error_count = 0
        self.total_warning_count = 0
        sublime.set_timeout(functools.partial(self._update_panel_main_thread, _NO_DIAGNOSTICS_PLACEHOLDER, []))
        self.panel_manager.ensure_log_panel()
        self._config_manager.add_change_listener(self)

    @property
    def window(self) -> sublime.Window:
        return self._window

    def get_and_clear_server_log(self) -> list[tuple[str, str]]:
        log = self._server_log
        self._server_log = []
        return log

    def get_config_manager(self) -> WindowConfigManager:
        return self._config_manager

    def get_sessions(self) -> Generator[Session, None, None]:
        yield from self._sessions

    def on_load_project_async(self) -> None:
        self.update_workspace_folders_async()
        self._config_manager.update()

    def on_post_save_project_async(self) -> None:
        if self.suppress_sessions_restart_on_project_update:
            self.suppress_sessions_restart_on_project_update = False
            return
        self.on_load_project_async()

    def update_workspace_folders_async(self) -> None:
        if self._workspace.update():
            workspace_folders = self._workspace.get_workspace_folders()
            for session in self._sessions:
                session.update_folders(workspace_folders)

    def enable_config_async(self, config_name: str) -> None:
        self._config_manager.enable_config(config_name)

    def disable_config_async(self, config_name: str) -> None:
        self._config_manager.disable_config(config_name)

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

    def listener_for_view(self, view: sublime.View) -> AbstractViewListener | None:
        for listener in self.listeners():
            if listener.view == view:
                return listener
        return None

    def _dequeue_listener_async(self) -> None:
        listener: AbstractViewListener | None = None
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
        scheme = parse_uri(listener.get_uri())[0]
        for session in self._sessions:
            if session.can_handle(listener.view, scheme, capability=None, inside_workspace=inside_workspace):
                # debug("registering session", session.config.name, "to listener", listener)
                try:
                    listener.on_session_initialized_async(session)
                except Exception as ex:
                    message = f"failed to register session {session.config.name} to listener {listener}"
                    exception_log(message, ex)

    def sessions(self, view: sublime.View, capability: str | None = None) -> Generator[Session, None, None]:
        inside_workspace = self._workspace.contains(view)
        sessions = list(self._sessions)
        uri = view.settings().get("lsp_uri")
        if not isinstance(uri, str):
            return
        scheme = parse_uri(uri)[0]
        for session in sessions:
            if session.can_handle(view, scheme, capability, inside_workspace):
                yield session

    def get_session(self, config_name: str, file_path: str) -> Session | None:
        return self._find_session(config_name, file_path)

    def _can_start_config(self, config_name: str, file_path: str) -> bool:
        return not bool(self._find_session(config_name, file_path))

    def _find_session(self, config_name: str, file_path: str) -> Session | None:
        inside = self._workspace.contains(file_path)
        for session in self._sessions:
            if session.config.name == config_name and session.handles_path(file_path, inside):
                return session
        return None

    def _needed_config(self, view: sublime.View) -> ClientConfig | None:
        configs = self._config_manager.match_view(view)
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
                plugin = get_plugin(config.name)
                if plugin and plugin.should_ignore(view):
                    debug(view, "ignored by plugin", plugin.__name__)
                else:
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
            cwd: str | None = None
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
                    message = f"cannot start {config.name}: {cannot_start_reason}"
                    self._config_manager.disable_config(config.name, only_for_session=True)
                    # Continue with handling pending listeners
                    self._new_session = None
                    sublime.set_timeout_async(self._dequeue_listener_async)
                    return self._window.status_message(message)
                cwd = plugin_class.on_pre_start(self._window, initiating_view, workspace_folders, config)
            config.set_view_status(initiating_view, "starting...")
            session = Session(self, self._create_logger(config.name), workspace_folders, config, plugin_class)
            if cwd:
                transport_cwd: str | None = cwd
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
            exception_log(f"Unable to start subprocess for {config.name}", e)
            if isinstance(e, CalledProcessError):
                print("Server output:\n{}".format(e.output.decode('utf-8', 'replace')))
            self._config_manager.disable_config(config.name, only_for_session=True)
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
                debug(f"Invalid logger type ({logger_type}) specified for log_server settings")
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

    def restart_sessions_async(self, config_name: str | None = None) -> None:
        self._end_sessions_async(config_name)
        listeners = list(self._listeners)
        self._listeners.clear()
        for listener in listeners:
            self.register_listener_async(listener)

    def _end_sessions_async(self, config_name: str | None = None) -> None:
        sessions = list(self._sessions)
        for session in sessions:
            if config_name is None or config_name == session.config.name:
                session.end_async()
                self._sessions.discard(session)

    def get_project_path(self, file_path: str) -> str | None:
        candidate: str | None = None
        for folder in self._workspace.folders:
            if file_path.startswith(folder):
                if candidate is None or len(folder) > len(candidate):
                    candidate = folder
        return candidate

    def should_ignore_diagnostics(self, uri: DocumentUri, configuration: ClientConfig) -> str | None:
        scheme, path = parse_uri(uri)
        if scheme != "file":
            return None
        if configuration.diagnostics_mode == "workspace" and not self._workspace.contains(path):
            return "not inside window folders"
        view = self._window.active_view()
        if not view:
            return None
        settings = view.settings()
        if matches_pattern(path, settings.get("binary_file_patterns")):
            return "matches a pattern in binary_file_patterns"
        if matches_pattern(path, settings.get("file_exclude_patterns")):
            return "matches a pattern in file_exclude_patterns"
        patterns = [sublime_pattern_to_glob(pattern, True) for pattern in settings.get("folder_exclude_patterns") or []]
        if matches_pattern(path, patterns):
            return "matches a pattern in folder_exclude_patterns"
        if self._workspace.includes_excluded_path(path):
            return "matches a project's folder_exclude_patterns"
        return None

    def on_post_exit_async(self, session: Session, exit_code: int, exception: Exception | None) -> None:
        self._sessions.discard(session)
        for listener in self._listeners:
            listener.on_session_shutdown_async(session)
        if exit_code != 0 or exception:
            config = session.config
            restart = self._config_manager.record_crash(config.name, exit_code, exception)
            if not restart:
                msg = "".join((
                    "The {0} server has crashed {1} times in the last {2} seconds.\n\n",
                    "You can try to Restart it or you can choose Cancel to disable it for this window for the ",
                    "duration of the current session. ",
                    "Re-enable by running \"LSP: Enable Language Server In Project\" from the Command Palette."
                )).format(config.name, RETRY_MAX_COUNT, int(RETRY_COUNT_TIMEDELTA.total_seconds()))
                if exception:
                    msg += f"\n\n--- Error: ---\n{str(exception)}"
                restart = sublime.ok_cancel_dialog(msg, "Restart")
            if restart:
                for listener in self._listeners:
                    self.register_listener_async(listener)
            else:
                self._config_manager.disable_config(config.name, only_for_session=True)

    def destroy(self) -> None:
        """
        This is called **from the main thread** when the plugin unloads. In that case we must destroy all sessions
        from the main thread. That could lead to some dict/list being mutated while iterated over, so be careful
        """
        self._end_sessions_async()
        if self.panel_manager:
            self.panel_manager.destroy_output_panels()
            self.panel_manager = None

    def handle_log_message(self, session: Session, params: LogMessageParams) -> None:
        if not userprefs().log_debug:
            return
        message_type = params['type']
        level = {
            MessageType.Error: "ERROR",
            MessageType.Warning: "WARNING",
            MessageType.Info: "INFO",
            MessageType.Log: "LOG",
            MessageType.Debug: "DEBUG"
        }.get(message_type, "?")
        message = params['message']
        print(f"{session.config.name}: {level}: {message}")
        if message_type == MessageType.Error:
            self.window.status_message(f"{session.config.name}: {message}")

    def handle_stderr_log(self, session: Session, message: str) -> None:
        self.handle_server_message_async(session.config.name, message)

    def handle_server_message_async(self, server_name: str, message: str) -> None:
        sublime.set_timeout(lambda: self.log_server_message(server_name, message))

    def log_server_message(self, prefix: str, message: str) -> None:
        self._server_log.append((prefix, message))
        list_len = len(self._server_log)
        max_lines = self.get_log_lines_limit()
        if list_len >= max_lines:
            # Trim leading items in the list, leaving only the max allowed count.
            del self._server_log[:list_len - max_lines]
        if self.panel_manager:
            self.panel_manager.update_log_panel()

    def get_log_lines_limit(self) -> int:
        return MAX_LOG_LINES_LIMIT_ON if self.is_log_lines_limit_enabled() else MAX_LOG_LINES_LIMIT_OFF

    def is_log_lines_limit_enabled(self) -> bool:
        panel = self.panel_manager and self.panel_manager.get_panel(PanelName.Log)
        return bool(panel and panel.settings().get(LOG_LINES_LIMIT_SETTING_NAME, True))

    def handle_show_message(self, session: Session, params: Any) -> None:
        sublime.status_message(f"{session.config.name}: {extract_message(params)}")

    def on_diagnostics_updated(self) -> None:
        self.total_error_count = 0
        self.total_warning_count = 0
        for session in self._sessions:
            local_errors, local_warnings = session.diagnostics.sum_total_errors_and_warnings_async()
            self.total_error_count += local_errors
            self.total_warning_count += local_warnings
        for listener in list(self._listeners):
            set_diagnostics_count(listener.view, self.total_error_count, self.total_warning_count)
        if self.panel_manager and self.panel_manager.is_panel_open(PanelName.Diagnostics):
            self.update_diagnostics_panel_async()

    def update_diagnostics_panel_async(self) -> None:
        to_render: list[str] = []
        prephantoms: list[tuple[int, int, str, str]] = []
        row = 0
        max_severity = userprefs().diagnostics_panel_include_severity_level
        contributions: OrderedDict[str, list[tuple[str, int | None, str | None, str | None]]] = OrderedDict()
        for session in self._sessions:
            for (_, path), contribution in session.diagnostics.filter_map_diagnostics_async(
                    is_severity_included(max_severity), lambda _, diagnostic: format_diagnostic_for_panel(diagnostic)):
                seen = path in contributions
                contributions.setdefault(path, []).extend(contribution)
                if not seen:
                    contributions.move_to_end(path)
        for path, contribution in contributions.items():
            to_render.append(f"{path}:")
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

    def _update_panel_main_thread(self, characters: str, prephantoms: list[tuple[int, int, str, str]]) -> None:
        panel = self.panel_manager and self.panel_manager.ensure_diagnostics_panel()
        if not panel or not panel.is_valid():
            return
        panel.run_command("lsp_update_panel", {"characters": characters})
        if self._panel_code_phantoms is None:
            self._panel_code_phantoms = sublime.PhantomSet(panel, "hrefs")
        phantoms: list[sublime.Phantom] = []
        for row, col, code, href in prephantoms:
            point = panel.text_point(row, col)
            region = sublime.Region(point, point)
            phantoms.append(sublime.Phantom(region, f"({make_link(href, code)})", sublime.PhantomLayout.INLINE))
        self._panel_code_phantoms.update(phantoms)

    # --- Implements WindowConfigChangeListener ------------------------------------------------------------------------

    def on_configs_changed(self, config_name: str | None = None) -> None:
        sublime.set_timeout_async(lambda: self.restart_sessions_async(config_name))


class WindowRegistry(LspSettingsChangeListener):
    def __init__(self) -> None:
        self._enabled = False
        self._windows: dict[int, WindowManager] = {}
        client_configs.set_listener(self)

    def enable(self) -> None:
        self._enabled = True
        # Initialize manually at plugin_loaded as we'll miss out on "on_new_window_async" events.
        for window in sublime.windows():
            self.lookup(window)

    def disable(self) -> None:
        self._enabled = False
        for wm in self._windows.values():
            try:
                wm.destroy()
            except Exception as ex:
                exception_log("failed to destroy window", ex)
        self._windows = {}

    def lookup(self, window: sublime.Window | None) -> WindowManager | None:
        if not self._enabled or not window or not window.is_valid():
            return None
        wm = self._windows.get(window.id())
        if wm:
            return wm
        workspace = ProjectFolders(window)
        window_config_manager = WindowConfigManager(window, client_configs.all)
        manager = WindowManager(window, workspace, window_config_manager)
        self._windows[window.id()] = manager
        return manager

    def listener_for_view(self, view: sublime.View) -> AbstractViewListener | None:
        manager = self.lookup(view.window())
        if not manager:
            return None
        return manager.listener_for_view(view)

    def discard(self, window: sublime.Window) -> None:
        wm = self._windows.pop(window.id(), None)
        if wm:
            sublime.set_timeout_async(wm.destroy)

    # --- Implements LspSettingsChangeListener -------------------------------------------------------------------------

    def on_client_config_updated(self, config_name: str | None = None) -> None:
        for wm in self._windows.values():
            wm.get_config_manager().update(config_name)

    def on_userprefs_updated(self) -> None:
        for wm in self._windows.values():
            wm.on_diagnostics_updated()
            for session in wm.get_sessions():
                sublime.set_timeout_async(session.on_userprefs_changed_async)


class RequestTimeTracker:
    def __init__(self) -> None:
        self._start_times: dict[int, float] = {}

    def start_tracking(self, request_id: int) -> None:
        self._start_times[request_id] = perf_counter()

    def end_tracking(self, request_id: int) -> str:
        duration = '-'
        if request_id in self._start_times:
            start = self._start_times.pop(request_id)
            duration_ms = perf_counter() - start
            duration = f'{int(duration_ms * 1000)}ms'
        return duration

    @classmethod
    def formatted_now(cls) -> str:
        now = datetime.now()
        return '{}.{:03d}'.format(now.strftime("%H:%M:%S"), int(now.microsecond / 1000))


class PanelLogger(Logger):

    def __init__(self, manager: WindowManager, server_name: str) -> None:
        self._manager = ref(manager)
        self._server_name = server_name
        self._request_time_tracker = RequestTimeTracker()

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
                params_str = f'<params with {len(params_str)} characters>'
            message = f"{message}: {params_str}"
            manager = self._manager()
            if manager is not None:
                manager.handle_server_message_async(":", message)

        sublime.set_timeout_async(run_on_async_worker_thread)

    def outgoing_response(self, request_id: Any, params: Any) -> None:
        if not userprefs().log_server:
            return
        duration = self._request_time_tracker.end_tracking(request_id)
        self.log(self._format_response(">>>", request_id, duration), params)

    def outgoing_error_response(self, request_id: Any, error: Error) -> None:
        if not userprefs().log_server:
            return
        duration = self._request_time_tracker.end_tracking(request_id)
        self.log(self._format_response("~~>", request_id, duration), error.to_lsp())

    def outgoing_request(self, request_id: int, method: str, params: Any) -> None:
        if not userprefs().log_server:
            return
        self._request_time_tracker.start_tracking(request_id)
        self.log(self._format_request("-->", method, request_id), params)

    def outgoing_notification(self, method: str, params: Any) -> None:
        if not userprefs().log_server:
            return
        self.log(self._format_notification(" ->", method), params)

    def incoming_response(self, request_id: int | None, params: Any, is_error: bool) -> None:
        if not userprefs().log_server:
            return
        direction = "<~~" if is_error else "<<<"
        duration = self._request_time_tracker.end_tracking(request_id) if request_id is not None else "-"
        self.log(self._format_response(direction, request_id, duration), params)

    def incoming_request(self, request_id: Any, method: str, params: Any) -> None:
        if not userprefs().log_server:
            return
        self._request_time_tracker.start_tracking(request_id)
        self.log(self._format_request("<--", method, request_id), params)

    def incoming_notification(self, method: str, params: Any, unhandled: bool) -> None:
        if not userprefs().log_server:
            return
        direction = "<? " if unhandled else "<- "
        self.log(self._format_notification(direction, method), params)

    def _format_response(self, direction: str, request_id: Any, duration: str) -> str:
        return "[{}] {} {} ({}) (duration: {})".format(
            RequestTimeTracker.formatted_now(), direction, self._server_name, request_id, duration)

    def _format_request(self, direction: str, method: str, request_id: Any) -> str:
        return f"[{RequestTimeTracker.formatted_now()}] {direction} {self._server_name} {method} ({request_id})"

    def _format_notification(self, direction: str, method: str) -> str:
        return f"[{RequestTimeTracker.formatted_now()}] {direction} {self._server_name} {method}"


class RemoteLogger(Logger):
    PORT = 9981
    DIRECTION_OUTGOING = 1
    DIRECTION_INCOMING = 2
    _ws_server: WebsocketServer | None = None
    _ws_server_thread: threading.Thread | None = None
    _last_id = 0

    def __init__(self, manager: WindowManager, server_name: str) -> None:
        RemoteLogger._last_id += 1
        self._server_name = f'{server_name} ({RemoteLogger._last_id})'
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

    def _on_new_client(self, client: dict, server: WebsocketServer) -> None:
        """Called for every client connecting (after handshake)."""
        debug("New client connected and was given id %d" % client['id'])
        # server.send_message_to_all("Hey all, a new client has joined us")

    def _on_client_left(self, client: dict, server: WebsocketServer) -> None:
        """Called for every client disconnecting."""
        debug("Client(%d) disconnected" % client['id'])

    def _on_message_received(self, client: dict, server: WebsocketServer, message: str) -> None:
        """Called when a client sends a message."""
        debug("Client(%d) said: %s" % (client['id'], message))

    def stderr_message(self, message: str) -> None:
        self._broadcast_json({
            'server': self._server_name,
            'time': round(perf_counter() * 1000),
            'method': 'stderr',
            'params': message,
            'isError': True,
            'direction': self.DIRECTION_INCOMING,
        })

    def outgoing_request(self, request_id: int, method: str, params: Any) -> None:
        self._broadcast_json({
            'server': self._server_name,
            'id': request_id,
            'time': round(perf_counter() * 1000),
            'method': method,
            'params': params,
            'direction': self.DIRECTION_OUTGOING,
        })

    def incoming_response(self, request_id: int | None, params: Any, is_error: bool) -> None:
        self._broadcast_json({
            'server': self._server_name,
            'id': request_id,
            'time': round(perf_counter() * 1000),
            'params': params,
            'direction': self.DIRECTION_INCOMING,
            'isError': is_error,
        })

    def incoming_request(self, request_id: Any, method: str, params: Any) -> None:
        self._broadcast_json({
            'server': self._server_name,
            'id': request_id,
            'time': round(perf_counter() * 1000),
            'method': method,
            'params': params,
            'direction': self.DIRECTION_INCOMING,
        })

    def outgoing_response(self, request_id: Any, params: Any) -> None:
        self._broadcast_json({
            'server': self._server_name,
            'id': request_id,
            'time': round(perf_counter() * 1000),
            'params': params,
            'direction': self.DIRECTION_OUTGOING,
        })

    def outgoing_error_response(self, request_id: Any, error: Error) -> None:
        self._broadcast_json({
            'server': self._server_name,
            'id': request_id,
            'isError': True,
            'params': error.to_lsp(),
            'time': round(perf_counter() * 1000),
            'direction': self.DIRECTION_OUTGOING,
        })

    def outgoing_notification(self, method: str, params: Any) -> None:
        self._broadcast_json({
            'server': self._server_name,
            'time': round(perf_counter() * 1000),
            'method': method,
            'params': params,
            'direction': self.DIRECTION_OUTGOING,
        })

    def incoming_notification(self, method: str, params: Any, unhandled: bool) -> None:
        self._broadcast_json({
            'server': self._server_name,
            'time': round(perf_counter() * 1000),
            'error': 'Unhandled notification!' if unhandled else None,
            'method': method,
            'params': params,
            'direction': self.DIRECTION_INCOMING,
        })

    def _broadcast_json(self, data: dict[str, Any]) -> None:
        if RemoteLogger._ws_server:
            json_data = json.dumps(data, sort_keys=True, check_circular=False, separators=(',', ':'))
            RemoteLogger._ws_server.send_message_to_all(json_data)


class RouterLogger(Logger):
    def __init__(self) -> None:
        self._loggers: list[Logger] = []

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
