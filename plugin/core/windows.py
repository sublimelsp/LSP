import re
from .events import global_events
from .logging import debug
from .types import ClientStates, ClientConfig, WindowLike, ViewLike, LanguageConfig
from .protocol import Notification
from .sessions import Session
from .url import filename_to_uri
from .workspace import get_project_path
try:
    from typing_extensions import Protocol
    from typing import Optional, List, Callable, Dict, Any
    from types import ModuleType
    assert Optional and List and Callable and Dict and Session and Any and ModuleType
    assert LanguageConfig
except ImportError:
    pass
    Protocol = object  # type: ignore


class ConfigRegistry(Protocol):
    # todo: calls config_for_scope immediately.
    all = []  # type: List[ClientConfig]

    def is_supported(self, view: ViewLike) -> bool:
        ...

    def scope_config(self, view: ViewLike, point: 'Optional[int]'=None) -> 'Optional[ClientConfig]':
        ...

    def syntax_configs(self, view: ViewLike) -> 'List[ClientConfig]':
        ...

    def syntax_supported(self, view: ViewLike) -> bool:
        ...

    def syntax_config_languages(self, view: ViewLike) -> 'Dict[str, LanguageConfig]':
        ...

    def update(self, configs: 'List[ClientConfig]') -> None:
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


def config_supports_syntax(config: 'ClientConfig', syntax: str) -> bool:
    for language in config.languages:
        if re.search(r'|'.join(r'\b%s\b' % re.escape(s) for s in language.syntaxes), syntax, re.IGNORECASE):
            return True
    return False


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

    def _get_applicable_sessions(self, view: ViewLike):
        sessions = []  # type: List[Session]
        syntax = view.settings().get("syntax")
        for config_name, session in self._sessions.items():
            if config_supports_syntax(session.config, syntax):
                sessions.append(session)
        return sessions

    def _notify_open_documents(self, session: Session) -> None:
        for file_name in self._document_states:
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
            for session in self._get_applicable_sessions(view):
                debug('closing', file_name, session.config.name)
                if session.client:
                    params = {"textDocument": {"uri": filename_to_uri(file_name)}}
                    session.client.send_notification(Notification.didClose(params))

    def handle_view_saved(self, view: ViewLike):
        file_name = view.file_name()
        if view.window() == self._window:
            if file_name in self._document_states:
                for session in self._get_applicable_sessions(view):
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
            if view.buffer_id() in self._pending_buffer_changes:
                del self._pending_buffer_changes[view.buffer_id()]

                for session in self._get_applicable_sessions(view):
                    if session.client:
                        document_state = self.get_document_state(file_name)
                        uri = filename_to_uri(file_name)
                        params = {
                            "textDocument": {
                                "uri": uri,
                                "languageId": self._view_language(view, session.config.name),
                                "version": document_state.inc_version(),
                            },
                            "contentChanges": [{
                                "text": view.substr(self._sublime.Region(0, view.size()))
                            }]
                        }
                        session.client.send_notification(Notification.didChange(params))


class WindowManager(object):
    def __init__(self, window: WindowLike, configs: ConfigRegistry, documents: DocumentHandler,
                 diagnostics: DiagnosticsHandler, session_starter: 'Callable', sublime: 'Any',
                 handler_dispatcher, on_closed: 'Optional[Callable]'=None) -> None:

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
        self._on_closed = on_closed

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
        startable_configs = filter(lambda c: c.enabled and c.name not in self._sessions,
                                   self._configs.syntax_configs(view))

        for config in startable_configs:
            debug("window {} requests {} for {}".format(self._window.id(), config.name, view.file_name()))
            self._start_client(config)

    def _start_client(self, config: ClientConfig):
        project_path = get_project_path(self._window)
        if project_path is None:
            debug('Cannot start without a project folder')
            return

        if self._can_start_config(config.name):
            if not self._handlers.on_start(config.name, self._window):
                return

            self._window.status_message("Starting " + config.name + "...")
            debug("starting in", project_path)
            session = self._start_session(self._window, project_path, config,
                                          lambda session: self._handle_session_started(session, project_path, config),
                                          lambda config_name: self._handle_session_ended(config_name))
            if session:
                debug("window {} added session {}".format(self._window.id(), config.name))
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
        self.end_sessions()

    def end_sessions(self) -> None:
        self._documents.reset()
        for config_name in list(self._sessions):
            self.end_session(config_name)

    def end_session(self, config_name: str) -> None:
        if config_name in self._sessions:
            debug("unloading session", config_name)
            self._sessions[config_name].end()

    def _end_old_sessions(self):
        if get_project_path(self._window) != self._project_path:
            debug('project path changed, ending existing sessions')
            self.end_sessions()

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

        self._handlers.on_initialized(config.name, self._window, client)

        document_sync = session.capabilities.get("textDocumentSync")
        if document_sync:
            self._documents.add_session(session)

        global_events.subscribe('view.on_close', lambda view: self._handle_view_closed(view, session))

        client.send_notification(Notification.initialized())
        if config.settings:
            configParams = {
                'settings': config.settings
            }
            client.send_notification(Notification.didChangeConfiguration(configParams))

        self._window.status_message("{} initialized".format(config.name))

    def _handle_view_closed(self, view, session):
        self._diagnostics.remove(view, session.config.name)
        self._sublime.set_timeout_async(lambda: self._check_window_closed(), 500)

    def _check_window_closed(self):
        debug('check window closed')

        if not self._window.is_valid():
            self._handle_window_closed()

    def _handle_window_closed(self):
        debug('window closed, ending sessions')
        self.end_sessions()

    def _handle_all_sessions_ended(self):
        debug('clients for window {} unloaded'.format(self._window.id()))
        if self._restarting:
            debug('restarting')
            self.start_active_views()
        elif not self._window.is_valid():
            debug('window no longer valid')
            if self._on_closed:
                self._on_closed()

    def _handle_session_ended(self, config_name):
        self._documents.remove_session(config_name)
        del self._sessions[config_name]
        for view in self._window.views():
            if view.file_name():
                self._diagnostics.remove(view, config_name)

        debug("session", config_name, "ended")
        if not self._sessions:
            self._handle_all_sessions_ended()

    def _handle_server_crash(self, config: ClientConfig):
        msg = "Language server {} has crashed, do you want to restart it?".format(config.name)
        result = self._sublime.ok_cancel_dialog(msg, ok_title="Restart")
        if result == self._sublime.DIALOG_YES:
            self.restart_sessions()


class WindowRegistry(object):
    def __init__(self, configs: GlobalConfigs, documents: 'Any', diagnostics: DiagnosticsHandler,
                 session_starter: 'Callable', sublime: 'Any', handler_dispatcher) -> None:
        self._windows = {}  # type: Dict[int, WindowManager]
        self._configs = configs
        self._diagnostics = diagnostics
        self._documents = documents
        self._session_starter = session_starter
        self._sublime = sublime
        self._handler_dispatcher = handler_dispatcher

    def lookup(self, window: 'Any') -> WindowManager:
        state = self._windows.get(window.id())
        if state is None:
            window_configs = self._configs.for_window(window)
            window_documents = self._documents.for_window(window, window_configs)
            state = WindowManager(window, window_configs, window_documents, self._diagnostics, self._session_starter,
                                  self._sublime, self._handler_dispatcher, lambda: self._on_closed(window))
            self._windows[window.id()] = state
        return state

    def _on_closed(self, window: WindowLike) -> None:
        if window.id() in self._windows:
            del self._windows[window.id()]
