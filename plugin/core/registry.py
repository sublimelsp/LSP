import sublime
import sublime_plugin
from .clients import start_window_config
from .configurations import ConfigManager, is_supported_syntax
from .handlers import LanguageHandler
from .logging import debug
from .rpc import Client
from .sessions import Session
from .settings import settings, client_configs
from .types import ClientConfig, ClientStates, WindowLike, view2scope
from .windows import WindowRegistry, DocumentHandlerFactory, WindowManager
from .typing import Optional, Callable, Dict, Any, Generator


client_start_listeners = {}  # type: Dict[str, Callable]
client_initialization_listeners = {}  # type: Dict[str, Callable]


class LSPViewEventListener(sublime_plugin.ViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        self._manager = None  # type: Optional[WindowManager]
        super().__init__(view)

    @classmethod
    def has_supported_syntax(cls, view_settings: dict) -> bool:
        syntax = view_settings.get('syntax')
        if syntax:
            return is_supported_syntax(syntax, client_configs.all)
        else:
            return False

    @property
    def manager(self) -> WindowManager:
        if not self._manager:
            self._manager = windows.lookup(self.view.window())

        assert self._manager
        return self._manager

    def has_manager(self) -> bool:
        return self._manager is not None


class LanguageHandlerDispatcher(object):

    def on_start(self, config_name: str, window: WindowLike) -> bool:
        if config_name in client_start_listeners:
            return client_start_listeners[config_name](window)
        else:
            return True

    def on_initialized(self, config_name: str, window: WindowLike, client: Client) -> None:
        if config_name in client_initialization_listeners:
            client_initialization_listeners[config_name](client)


def load_handlers() -> None:
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


def client_from_session(session: Optional[Session]) -> Optional[Client]:
    return session.client if session else None


def sessions_for_view(view: sublime.View) -> Generator[Session, None, None]:
    yield from _sessions_for_view_and_window(view, view.window())


def session_for_view(view: sublime.View, capability: str, point: int) -> Optional[Session]:
    """
    returns the "best matching" session for that particular point. This is determined by the feature_selector property
    of the relevant LanguageConfig.
    """
    sessions = [s for s in sessions_for_view(view) if s.has_capability(capability)]
    if not sessions:
        return None
    scope = view2scope(view)
    return max(sessions, key=lambda session: session.config.score_feature(scope))


def _sessions_for_view_and_window(view: sublime.View,
                                  window: Optional[sublime.Window]) -> Generator[Session, None, None]:
    if window:
        file_path = view.file_name()
        if file_path:
            manager = windows.lookup(window)
            for config in manager._configs.match_view(view):
                session = manager.get_session(config.name, file_path)
                if session and session.state == ClientStates.READY:
                    yield session


def unload_sessions(window: sublime.Window) -> None:
    wm = windows.lookup(window)
    wm.end_sessions()


configs = ConfigManager(client_configs.all)
client_configs.set_listener(configs.update)
documents = DocumentHandlerFactory(sublime, settings)
handlers_dispatcher = LanguageHandlerDispatcher()
windows = WindowRegistry(configs, documents, start_window_config, sublime, handlers_dispatcher)


def configurations_for_view(view: sublime.View) -> Generator[ClientConfig, None, None]:
    window = view.window()
    if window:
        # todo: don't expose _configs
        yield from windows.lookup(window)._configs.match_view(view)


def is_supported_view(view: sublime.View) -> bool:
    # TODO: perhaps make this check for a client instead of a config
    return any(configurations_for_view(view))


class LspTextCommand(sublime_plugin.TextCommand):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)

    def is_visible(self, event: Optional[dict] = None) -> bool:
        return is_supported_view(self.view)

    def has_client_with_capability(self, capability: str) -> bool:
        return session_for_view(self.view, capability, self.view.sel()[0]) is not None

    def client_with_capability(self, capability: str) -> Optional[Client]:
        return client_from_session(session_for_view(self.view, capability, self.view.sel()[0]))


class LspRestartClientCommand(sublime_plugin.TextCommand):
    def is_enabled(self) -> bool:
        return is_supported_view(self.view)

    def run(self, edit: Any) -> None:
        window = self.view.window()
        if window:
            windows.lookup(window).restart_sessions()
