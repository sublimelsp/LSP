import sublime
import sublime_plugin
from .clients import start_window_config
from .configurations import ConfigManager, is_supported_syntax
from .handlers import LanguageHandler
from .logging import debug
from .rpc import Client
from .sessions import Session
from .settings import settings, client_configs
from .types import ClientConfig, WindowLike
from .windows import WindowRegistry, DocumentHandlerFactory, WindowManager
from .typing import Optional, Callable, Dict, Any, Iterable


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


def sessions_for_view(view: sublime.View, point: Optional[int] = None) -> Iterable[Session]:
    return _sessions_for_view_and_window(view, view.window(), point)


def session_for_view(view: sublime.View,
                     capability: str,
                     point: Optional[int] = None) -> Optional[Session]:
    return next((session for session in sessions_for_view(view, point)
                 if session.has_capability(capability)), None)


def _sessions_for_view_and_window(view: sublime.View, window: Optional[sublime.Window],
                                  point: Optional[int] = None) -> Iterable[Session]:
    if not window:
        debug("no window for view", view.file_name())
        return []

    file_path = view.file_name()
    if not file_path:
        # debug("no session for unsaved file")
        return []

    manager = windows.lookup(window)
    scope_configs = manager._configs.scope_configs(view, point)
    for config in scope_configs:
        session = manager.get_session(config.name, file_path)
        if session:
            yield session


def unload_sessions(window: sublime.Window) -> None:
    wm = windows.lookup(window)
    wm.end_sessions()


configs = ConfigManager(client_configs.all)
client_configs.set_listener(configs.update)
documents = DocumentHandlerFactory(sublime, settings)
handlers_dispatcher = LanguageHandlerDispatcher()
windows = WindowRegistry(configs, documents, start_window_config, sublime, handlers_dispatcher)


def configs_for_scope(view: Any, point: Optional[int] = None) -> Iterable[ClientConfig]:
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
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)

    def is_visible(self, event: Optional[dict] = None) -> bool:
        return is_supported_view(self.view)

    def has_client_with_capability(self, capability: str) -> bool:
        return session_for_view(self.view, capability) is not None

    def client_with_capability(self, capability: str) -> Optional[Client]:
        return client_from_session(session_for_view(self.view, capability))


class LspRestartClientCommand(sublime_plugin.TextCommand):
    def is_enabled(self) -> bool:
        return is_supported_view(self.view)

    def run(self, edit: Any) -> None:
        window = self.view.window()
        if window:
            windows.lookup(window).restart_sessions()
