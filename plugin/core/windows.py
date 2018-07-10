from .sessions import Session
from .logging import debug
from .types import ClientStates, ClientConfig
from .protocol import Notification
from .workspace import get_project_path


class WindowLike(object):
    def id(self):
        return 0


class ViewLike(object):
    def __init__(self):
        pass


class ConfigRegistry(object):
    def is_supported(self, view: ViewLike) -> bool:
        # todo: calls config_for_scope immediately.
        pass

    def scope_config(self, view: ViewLike) -> 'Optional[ClientConfig]':
        pass


class DiagnosticsHandler(object):
    def update(window: WindowLike, client_name: str, update: dict):
        pass

    def remove(view: ViewLike, client_name: str):
        pass


class DocumentHandler(object):
    def initialize(text_document_sync_kind):
        pass

    def notify_did_open(view: ViewLike):
        pass


def get_active_views(window: WindowLike):
    views = list()  # type: List[sublime.View]
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
                 diagnostics: DiagnosticsHandler, session_starter: 'Callable'):

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

    def get_session(self, config_name: str) -> 'Optional[Session]':
        return self._sessions.get(config_name)

    def add_session(self, config_name: str, session: Session) -> None:
        if config_name not in self._sessions:
            self._sessions[config_name] = session
        else:
            raise Exception("session already added")

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
        startable_views = list(filter(self._configs.is_supported, active_views))

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
                debug(config.name, 'is not enabled')

    def _start_client(self, view: ViewLike, config: ClientConfig):
        project_path = get_project_path(self._window)
        if project_path is None:
            debug('Cannot start without a project folder')
            return

        if self._can_start_config(config.name):
            # TODO: re-enable
            # if config.name in client_start_listeners:
                # handler_startup_hook = client_start_listeners[config.name]
                # if not handler_startup_hook(window):
                #     return

            # if settings.show_status_messages:
            #     self._window.status_message("Starting " + config.name + "...")
            debug("starting in", project_path)
            session = self._start_session(self._window, project_path, config,
                                          lambda session: self._handle_session_started(session, project_path, config))
            self._sessions[config.name] = session
        else:
            debug('Already starting on this window:', config.name)

    def _handle_session_started(self, session, project_path, config):
        client = session.client
        # client.set_crash_handler(lambda: handle_server_crash(self._window, config))
        # client.set_error_display_handler(lambda msg: sublime.status_message(msg))

        # # handle server requests and notifications
        # client.on_request(
        #     "workspace/applyEdit",
        #     lambda params: apply_workspace_edit(self._window, params))

        # client.on_request(
        #     "window/showMessageRequest",
        #     lambda params: handle_message_request(params))

        client.on_notification(
            "textDocument/publishDiagnostics",
            lambda params: self._diagnostics.update(self._window, config.name, params))

        # client.on_notification(
        #     "window/showMessage",
        #     lambda params: sublime.message_dialog(params.get("message")))

        # if settings.log_server:
        #     client.on_notification(
        #         "window/logMessage",
        #         lambda params: server_log(params.get("message")))

        # if config.name in client_initialization_listeners:
        #     client_initialization_listeners[config.name](client)

        # TODO: These handlers is already filtered by syntax but does not need to
        # be enabled 2x per client
        # Move filtering?
        document_sync = session.capabilities.get("textDocumentSync")
        if document_sync:
            self._documents.initialize(document_sync)

        # Events.subscribe('view.on_close', lambda view: self._diagnostics.remove(view, config.name))

        client.send_notification(Notification.initialized())
        if config.settings:
            configParams = {
                'settings': config.settings
            }
            client.send_notification(Notification.didChangeConfiguration(configParams))

        for view in self._open_after_initialize:
            self._documents.notify_did_open(view)

        # if settings.show_status_messages:
        #     window.status_message("{} initialized".format(config.name))
        self._open_after_initialize.clear()


class WindowRegistry(object):
    def __init__(self, configs: ConfigRegistry, documents: DocumentHandler, diagnostics: DiagnosticsHandler,
                 session_starter: 'Callable'):
        self._windows = {}  # type: Dict[int, WindowManager]
        self._configs = configs
        self._diagnostics = diagnostics
        self._documents = documents
        self._session_starter = session_starter

    def lookup(self, window: WindowLike) -> WindowManager:
        state = self._windows.get(window.id())
        if state is None:
            state = WindowManager(window, self._configs, self._documents, self._diagnostics, self._session_starter)
            self._windows[window.id()] = state
        return state
