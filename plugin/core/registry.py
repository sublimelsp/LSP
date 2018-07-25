import sublime
import sublime_plugin

from .documents import (
    DocumentHandlerFactory
)
from .diagnostics import GlobalDiagnostics
from .windows import WindowRegistry
from .configurations import (
	ConfigManager, register_client_config
)
from .settings import (
    settings
)
from .clients import (
    start_window_config
)
from .types import ClientStates
from .handlers import LanguageHandler
from .logging import debug


client_start_listeners = {}  # type: Dict[str, Callable]
client_initialization_listeners = {}  # type: Dict[str, Callable]


class LanguageHandlerDispatcher(object):

    def on_start(self, config_name: str) -> bool:
        if config_name in client_start_listeners:
            return client_start_listeners[config_name]()
        else:
            return True

    def on_initialized(self, config_name: str, client):
        if config_name in client_initialization_listeners:
            client_initialization_listeners[config_name](client)

def load_handlers():
    for handler in LanguageHandler.instantiate_all():
        register_language_handler(handler)


def register_language_handler(handler: LanguageHandler) -> None:
    debug("received config {} from {}".format(handler.name, handler.__class__.__name__))
    register_client_config(handler.config)
    if handler.on_start:
        client_start_listeners[handler.name] = handler.on_start
    if handler.on_initialized:
        client_initialization_listeners[handler.name] = handler.on_initialized


def client_for_view(view: sublime.View) -> 'Optional[Client]':
    return _client_for_view_and_window(view, view.window())


def session_for_view(view: sublime.View) -> 'Optional[Session]':
    return _session_for_view_and_window(view, view.window())


def _session_for_view_and_window(view: sublime.View, window: 'Optional[sublime.Window]') -> 'Optional[Session]':
    if not window:
        debug("no window for view", view.file_name())
        return None


    config = config_for_scope(view)
    if not config:
        debug("config not available for view", view.file_name())
        return None

    session = windows.lookup(window).get_session(config.name)
    if session.state == ClientStates.READY:
    	return session
    else:
    	return None

    # window_config_states = window_configs(window)
    # if config.name not in window_config_states:
    #     debug(config.name, "not available for view",
    #           view.file_name(), "in window", window.id())
    #     return None
    # else:
    #     session = window_config_states[config.name]
    #     if session.state == ClientStates.READY:
    #         return session
    #     else:
    #         return None


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



class SublimeUI(object):
    DIALOG_CANCEL = sublime.DIALOG_CANCEL
    DIALOG_YES = sublime.DIALOG_YES
    DIALOG_NO = sublime.DIALOG_NO

    def message_dialog(self, msg: str) -> None:
        sublime.message_dialog(msg)

    def ok_cancel_dialog(self, msg: str, ok_title: str) -> bool:
        return sublime.ok_cancel_dialog(msg, ok_title)

    def yes_no_cancel_dialog(self, msg, yes_title: str, no_title: str) -> int:
        return sublime.yes_no_cancel_dialog(msg, yes_title, no_title)


configs = ConfigManager()
diagnostics = GlobalDiagnostics()
documents = DocumentHandlerFactory()
handlers_dispatcher = LanguageHandlerDispatcher()
windows = WindowRegistry(configs, documents, diagnostics, start_window_config, SublimeUI(), handlers_dispatcher)

def config_for_scope(view: 'Any') -> 'Optional[ClientConfig]':
    window = view.window()
    if window:
        # todo: don't expose _configs
        return windows.lookup(window)._configs.scope_config(view)

def is_supported_view(view: sublime.View) -> bool:
    # TODO: perhaps make this check for a client instead of a config
    if config_for_scope(view):
        return True
    else:
        return False


class LspRestartClientCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        return is_supported_view(self.view)

    def run(self, edit):
        window = self.view.window()
        if window:
            windows.lookup(window).restart_sessions()


class LspStartClientCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        return is_supported_view(self.view)

    def run(self, edit):
        start_active_window()


