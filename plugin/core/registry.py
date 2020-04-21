import sublime
import sublime_plugin
from .configurations import ConfigManager, is_supported_syntax
from .logging import debug
from .rpc import Client
from .sessions import Session
from .settings import settings, client_configs
from .types import ClientConfig, ClientStates
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


def client_from_session(session: Optional[Session]) -> Optional[Client]:
    return session if session else None


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
    sessions = (manager.get_session(config.name, file_path) for config in scope_configs)
    ready_sessions = (session for session in sessions if session and session.state == ClientStates.READY)
    return ready_sessions


def unload_sessions(window: sublime.Window) -> None:
    wm = windows.lookup(window)
    wm.end_sessions()


configs = ConfigManager(client_configs.all)
client_configs.set_listener(configs.update)
documents = DocumentHandlerFactory(sublime, settings)
windows = WindowRegistry(configs, documents, sublime)


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
