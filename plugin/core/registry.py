import sublime
import sublime_plugin
from .windows import WindowRegistry, DocumentHandlerFactory
from .configurations import (
    ConfigManager
)
from .clients import (
    start_window_config
)
from .types import ClientStates, ClientConfig
from .handlers import LanguageHandler
from .logging import debug
from .sessions import Session
from .clients import Client
from .settings import settings, client_configs

try:
    from typing import Optional, List, Callable, Dict, Any
    assert Optional and List and Callable and Dict and Any and ClientConfig and Client and Session
except ImportError:
    pass


client_start_listeners = {}  # type: Dict[str, Callable]
client_initialization_listeners = {}  # type: Dict[str, Callable]


class LanguageHandlerDispatcher(object):

    def on_start(self, config_name: str, window) -> bool:
        if config_name in client_start_listeners:
            return client_start_listeners[config_name](window)
        else:
            return True

    def on_initialized(self, config_name: str, window, client):
        if config_name in client_initialization_listeners:
            client_initialization_listeners[config_name](client)


def load_handlers():
    for handler in LanguageHandler.instantiate_all():
        register_language_handler(handler)
    client_configs.update_configs()


def register_language_handler(handler: LanguageHandler) -> None:
    debug("received config {} from {}".format(handler.name, handler.__class__.__name__))
    client_configs.add_external_config(handler.config)
    if handler.on_start:
        client_start_listeners[handler.name] = handler.on_start
    if handler.on_initialized:
        client_initialization_listeners[handler.name] = handler.on_initialized


def client_for_view(view: sublime.View) -> 'Optional[Client]':
    return _client_for_view_and_window(view, view.window())


def session_for_view(view: sublime.View, point: 'Optional[int]' = None) -> 'Optional[Session]':
    return _session_for_view_and_window(view, view.window(), point)


def _session_for_view_and_window(view: sublime.View, window: 'Optional[sublime.Window]',
                                 point=None) -> 'Optional[Session]':
    if not window:
        debug("no window for view", view.file_name())
        return None

    config = config_for_scope(view, point)
    if not config:
        debug("no config found or enabled for view", view.file_name())
        return None

    session = windows.lookup(window).get_session(config.name)
    if session:
        if session.state == ClientStates.READY:
            return session
    return None


def _client_for_view_and_window(view: sublime.View, window: 'Optional[sublime.Window]') -> 'Optional[Client]':
    session = _session_for_view_and_window(view, window)

    if session:
        if session.client:
            return session.client
        else:
            debug(session.config.name, "in state", session.state, " for view",
                  view.file_name())
            return None
    else:
        debug('no session found')
        return None


def unload_sessions():
    for window in sublime.windows():
        wm = windows.lookup(window)
        wm.end_sessions()


configs = ConfigManager(client_configs.all)
documents = DocumentHandlerFactory(sublime, settings)
handlers_dispatcher = LanguageHandlerDispatcher()
windows = WindowRegistry(configs, documents, start_window_config, sublime, handlers_dispatcher)


def config_for_scope(view: 'Any', point=None) -> 'Optional[ClientConfig]':
    window = view.window()
    if window:
        # todo: don't expose _configs
        return windows.lookup(window)._configs.scope_config(view, point)
    return None


def is_supported_view(view: sublime.View) -> bool:
    # TODO: perhaps make this check for a client instead of a config
    if config_for_scope(view):
        return True
    else:
        return False


class LspTextCommand(sublime_plugin.TextCommand):
    def __init__(self, view):
        super().__init__(view)

    def is_visible(self, event=None):
        return is_supported_view(self.view)

    def has_client_with_capability(self, capability):
        session = session_for_view(self.view)
        if session and session.has_capability(capability):
            return True
        return False


class LspRestartClientCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        return is_supported_view(self.view)

    def run(self, edit):
        window = self.view.window()
        if window:
            windows.lookup(window).restart_sessions()
