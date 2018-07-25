from .events import Events
from .logging import debug
from .types import ClientStates, ClientConfig, WindowLike, ViewLike, SublimeGlobal
from .protocol import Notification
from .sessions import Session
from .workspace import get_project_path
try:
    from typing_extensions import Protocol
    from typing import Optional, List, Callable, Dict
    assert Optional and List and Callable and Dict and Session
except ImportError:
    pass
    Protocol = object  # type: ignore


class ConfigRegistry(Protocol):
    # todo: calls config_for_scope immediately.
    def is_supported(self, view: ViewLike) -> bool:
        ...

    def scope_config(self, view: ViewLike) -> 'Optional[ClientConfig]':
        ...


class GlobalConfigs(Protocol):
    def for_window(self, window: WindowLike) -> ConfigRegistry:
        ...


class DiagnosticsHandler(Protocol):
    def update(self, window: WindowLike, client_name: str, update: dict) -> None:
        ...

    def remove(self, view: ViewLike, client_name: str) -> None:
        ...


class DocumentHandler(Protocol):
    def initialize(self, text_document_sync_kind) -> None:
        ...

    def notify_did_open(self, view: ViewLike) -> None:
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


class WindowManager(object):
    def __init__(self, window: WindowLike, configs: ConfigRegistry, documents: DocumentHandler,
                 diagnostics: DiagnosticsHandler, session_starter: 'Callable', sublime: SublimeGlobal,
                 handler_dispatcher) -> None:

        # to move here:
        # configurations.py: window_client_configs and all references
        # clients.py: clients_by_window and all references
        self._window = window
        self._configs = configs
        self._diagnostics = diagnostics
        self._documents = documents
        self._sessions = dict()  # type: Dict[str, Session]
        self._start_session = session_starter
        self._open_after_initialize = []  # type: List[ViewLike]
        self._sublime = sublime
        self._handlers = handler_dispatcher
        self._restarting = False

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

    def start_active_views(self):
        active_views = get_active_views(self._window)
        startable_views = list(filter(self._configs.is_supported, active_views))  # type: List[ViewLike]

        if len(startable_views) > 0:
            first_view = startable_views.pop(0)
            debug('starting active=', first_view.file_name(), 'other=', len(startable_views))
            self._initialize_on_open(first_view)
            if len(startable_views) > 0:
                for view in startable_views:
                    self._open_after_initialize.append(view)

    def activate_view(self, view: ViewLike):
        # TODO: we can shortcut here by checking documentstate.
        self._initialize_on_open(view)

    def _initialize_on_open(self, view: ViewLike):
        debug("initialize on open", self._window.id(), view.file_name())

        # TODO: move this back to main.py?
        # if window_configs(window):
        #     unload_old_clients(window)

        self._open_after_initialize = []
        config = self._configs.scope_config(view)
        if config:
            if config.enabled:
                if not self._is_session_ready(config.name):
                    # TODO: this assumes the 2nd, 3rd, 4th view all have the same config
                    self._open_after_initialize.append(view)
                    self._start_client(view, config)
                else:
                    debug('session already ready', config.name)
            else:
                debug(config.name, 'is not enabled')

    def _start_client(self, view: ViewLike, config: ClientConfig):
        project_path = get_project_path(self._window)
        if project_path is None:
            debug('Cannot start without a project folder')
            return

        if self._can_start_config(config.name):
            if not self._handlers.on_start(config.name):
                return

            self._window.status_message("Starting " + config.name + "...")
            debug("starting in", project_path)
            session = self._start_session(self._window, project_path, config,
                                          lambda session: self._handle_session_started(session, project_path, config),
                                          lambda config_name: self._handle_session_ended(config_name))
            self._sessions[config.name] = session
        else:
            debug('Already starting on this window:', config.name)

    def _handle_message_request(self, params: dict):
        message = params.get("message", "(missing message)")
        actions = params.get("actions", [])
        addendum = "TODO: showMessageRequest with actions:"
        titles = list(action.get("title") for action in actions)
        self._sublime.message_dialog("\n".join([message, addendum] + titles))

    def restart_sessions(self):
        self._restarting = True
        self._documents.reset(self._window)
        for config_name in list(self._sessions):
            debug("unloading session", config_name)
            self._sessions[config_name].end()

    def _apply_workspace_edit(self, params):
        edit = params.get('edit', dict())
        self._window.run_command('lsp_apply_workspace_edit', {'changes': edit.get('changes'),
                                                              'documentChanges': edit.get('documentChanges')})

    def _handle_session_started(self, session, project_path, config):
        client = session.client
        client.set_crash_handler(lambda: self._handle_server_crash(config))
        client.set_error_display_handler(lambda msg: self._window.status_message(msg))

        # handle server requests and notifications
        client.on_request(
            "workspace/applyEdit",
            lambda params: self._apply_workspace_edit(params))

        client.on_request(
            "window/showMessageRequest",
            lambda params: self._handle_message_request(params))

        client.on_notification(
            "textDocument/publishDiagnostics",
            lambda params: self._diagnostics.update(self._window, config.name, params))

        client.on_notification(
            "window/showMessage",
            lambda params: self._sublime.message_dialog(params.get("message")))

        self._handlers.on_initialized(config.name, client)

        # TODO: These handlers is already filtered by syntax but does not need to
        # be enabled 2x per client
        # Move filtering?
        document_sync = session.capabilities.get("textDocumentSync")
        if document_sync:
            self._documents.initialize(Events, session)

        Events.subscribe('view.on_close', lambda view: self._handle_view_closed(view, session))

        client.send_notification(Notification.initialized())
        if config.settings:
            configParams = {
                'settings': config.settings
            }
            client.send_notification(Notification.didChangeConfiguration(configParams))

        for view in self._open_after_initialize:
            self._documents.notify_did_open(view)

        self._window.status_message("{} initialized".format(config.name))
        self._open_after_initialize.clear()

    def _handle_view_closed(self, view, session):
        self._diagnostics.remove(view, session.config.name)
        # todo: sublime.set_timeout_async(check_window_unloaded, 500)

    def _handle_all_sessions_ended(self):
        debug('clients for window {} unloaded'.format(self._window.id()))
        if self._restarting:
            debug('restarting')
            self.start_active_views()

    def _handle_session_ended(self, config_name):
        del self._sessions[config_name]
        debug("session", config_name, "ended")
        if not self._sessions:
            self._handle_all_sessions_ended()

    def _handle_server_crash(self, config: ClientConfig):
        msg = "Language server {} has crashed, do you want to restart it?".format(config.name)
        result = self._sublime.ok_cancel_dialog(msg, ok_title="Restart")
        if result == self._sublime.DIALOG_YES:
            self.restart_sessions()


class WindowRegistry(object):
    def __init__(self, configs: ConfigRegistry, documents: 'Any', diagnostics: DiagnosticsHandler,
                 session_starter: 'Callable', sublime: SublimeGlobal, handler_dispatcher) -> None:
        self._windows = {}  # type: Dict[int, WindowManager]
        self._configs = configs
        self._diagnostics = diagnostics
        self._documents = documents
        self._session_starter = session_starter
        self._sublime = sublime
        self._handler_dispatcher = handler_dispatcher

    def lookup(self, window: WindowLike) -> WindowManager:
        state = self._windows.get(window.id())
        if state is None:
            window_configs = self._configs.for_window(window)
            window_documents = self._documents.for_window()
            state = WindowManager(window, window_configs, window_documents, self._diagnostics, self._session_starter,
                                  self._sublime, self._handler_dispatcher)
            self._windows[window.id()] = state
        return state
