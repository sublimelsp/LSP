import sublime
import sublime_plugin
from .configurations import ConfigManager, is_supported_syntax
from .rpc import Client
from .sessions import Session
from .settings import settings, client_configs
from .types import ClientConfig, ClientStates, view2scope
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


def client_from_session(session: Optional[Session]) -> Optional[Client]:
    return session if session else None


def sessions_for_view(view: sublime.View, capability: Optional[str] = None) -> Generator[Session, None, None]:
    """
    Returns all sessions for this view, optionally matching the capability path.
    """
    yield from _sessions_for_view_and_window(view, view.window(), capability)


def session_for_view(view: sublime.View, capability: str, point: Optional[int] = None) -> Optional[Session]:
    """
    returns the "best matching" session for that particular point. This is determined by the feature_selector property
    of the relevant LanguageConfig.

    If point is None, then the point is understood to be the position of the first cursor.
    """
    if point is None:
        try:
            point = view.sel()[0].b
        except IndexError:
            return None
    scope = view.scope_name(point)
    try:
        return max(sessions_for_view(view, capability), key=lambda session: session.config.score_feature(scope))
    except ValueError:
        return None


def _sessions_for_view_and_window(view: sublime.View, window: Optional[sublime.Window],
                                  capability: Optional[str]) -> Generator[Session, None, None]:
    if window:
        file_path = view.file_name()
        if file_path:
            manager = windows.lookup(window)
            scope = view2scope(view)
            for sessions in manager._sessions.values():
                for session in sessions:
                    if session.state == ClientStates.READY and session.config.match_document(scope):
                        if session.handles_path(file_path):
                            if capability is None or session.has_capability(capability):
                                yield session


def unload_sessions(window: sublime.Window) -> None:
    wm = windows.lookup(window)
    wm.end_sessions()


configs = ConfigManager(client_configs.all)
client_configs.set_listener(configs.update)
documents = DocumentHandlerFactory(sublime, settings)
windows = WindowRegistry(configs, documents, sublime)


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
