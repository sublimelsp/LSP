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
    from typing import Optional, List, Callable, Dict, Any, Iterable
    assert Optional and List and Callable and Dict and Any and ClientConfig and Client and Session and Iterable
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


def client_from_session(session: 'Optional[Session]') -> 'Optional[Client]':
    if session:
        if session.client:
            return session.client
        else:
            debug(session.config.name, "in state", session.state)
            return None
    else:
        debug('no session found')
        return None


def sessions_for_view(view: sublime.View, point: 'Optional[int]' = None) -> 'Iterable[Session]':
    return _sessions_for_view_and_window(view, view.window(), point)


def session_for_view(view: sublime.View,
                     capability: str,
                     point: 'Optional[int]' = None) -> 'Optional[Session]':
    return next((session for session in sessions_for_view(view, point)
                 if session.has_capability(capability)), None)


def _sessions_for_view_and_window(view: sublime.View, window: 'Optional[sublime.Window]',
                                  point=None) -> 'Iterable[Session]':
    if not window:
        debug("no window for view", view.file_name())
        return []

    manager = windows.lookup(window)
    scope_configs = manager._configs.scope_configs(view, point)
    sessions = (manager.get_session(config.name) for config in scope_configs)
    ready_sessions = (session for session in sessions if session and session.state == ClientStates.READY)
    return ready_sessions


def unload_sessions(window):
    wm = windows.lookup(window)
    wm.end_sessions()


configs = ConfigManager(client_configs.all)
client_configs.set_listener(configs.update)
documents = DocumentHandlerFactory(sublime, settings)
handlers_dispatcher = LanguageHandlerDispatcher()
windows = WindowRegistry(configs, documents, start_window_config, sublime, handlers_dispatcher)


def configs_for_scope(view: 'Any', point=None) -> 'Iterable[ClientConfig]':
    window = view.window()
    if window:
        # todo: don't expose _configs
        return windows.lookup(window)._configs.scope_configs(view, point)
    return []


def is_supported_view(view: sublime.View) -> bool:
    # TODO: perhaps make this check for a client instead of a config
    if configs_for_scope(view):
        return True
    else:
        return False


class LspTextCommand(sublime_plugin.TextCommand):
    def __init__(self, view):
        super().__init__(view)

    def is_visible(self, event=None) -> bool:
        return is_supported_view(self.view)

    def has_client_with_capability(self, capability) -> bool:
        return session_for_view(self.view, capability) is not None

    def client_with_capability(self, capability) -> 'Optional[Client]':
        return client_from_session(session_for_view(self.view, capability))


class LspRestartClientCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        return is_supported_view(self.view)

    def run(self, edit):
        window = self.view.window()
        if window:
            windows.lookup(window).restart_sessions()
