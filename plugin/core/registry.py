from .configurations import ConfigManager
from .sessions import Session
from .settings import client_configs
from .settings import settings, client_configs
from .types import ClientConfig, ClientStates, view2scope
from .typing import Optional, Callable, Dict, Any, Generator
from .windows import WindowRegistry, WindowManager
import sublime
import sublime_plugin


client_start_listeners = {}  # type: Dict[str, Callable]
client_initialization_listeners = {}  # type: Dict[str, Callable]


class LSPViewEventListener(sublime_plugin.ViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        self._manager = None  # type: Optional[WindowManager]
        super().__init__(view)

    @classmethod
    def has_supported_syntax(cls, view_settings: dict) -> bool:
        syntax = view_settings.get('syntax')
        return bool(syntax and client_configs.is_syntax_supported(syntax))

    @property
    def manager(self) -> WindowManager:
        if not self._manager:
            self._manager = windows.lookup(self.view.window())

        assert self._manager
        return self._manager

    def has_manager(self) -> bool:
        return self._manager is not None

    def purge_changes(self) -> None:
        # Supermassive hack that will go away later.
        listeners = sublime_plugin.view_event_listeners.get(self.view.id(), [])
        for listener in listeners:
            if listener.__class__.__name__ == 'DocumentSyncListener':
                listener.purge_changes()  # type: ignore
                return


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
        manager = windows.lookup(window)
        yield from manager.sessions(view, capability)


def unload_sessions(window: sublime.Window) -> None:
    wm = windows.lookup(window)
    wm.end_sessions()


configs = ConfigManager(client_configs.all)
client_configs.set_listener(configs.update)
windows = WindowRegistry(configs, sublime)


def configurations_for_view(view: sublime.View) -> Generator[ClientConfig, None, None]:
    window = view.window()
    if window:
        # todo: don't expose _configs
        yield from windows.lookup(window)._configs.match_view(view)


def get_position(view: sublime.View, event: Optional[dict] = None) -> int:
    if event:
        return view.window_to_text((event["x"], event["y"]))
    else:
        return view.sel()[0].begin()


class LspTextCommand(sublime_plugin.TextCommand):

    capability = ''

    def is_visible(self, event: Optional[dict] = None) -> bool:
        if self.capability:
            # At least one active session with the given capability must exist.
            return bool(self.session(self.capability, get_position(self.view, event)))
        else:
            # Any session will do.
            return any(self.sessions())

    def is_enabled(self, event: Optional[dict] = None) -> bool:
        return self.is_visible(event)

    def want_event(self) -> bool:
        return True

    def session(self, capability: str, point: Optional[int] = None) -> Optional[Session]:
        return session_for_view(self.view, capability, point)

    def sessions(self, capability: Optional[str] = None) -> Generator[Session, None, None]:
        yield from sessions_for_view(self.view, capability)


class LspRestartClientCommand(sublime_plugin.TextCommand):
    def run(self, edit: Any) -> None:
        window = self.view.window()
        if window:
            windows.lookup(window).restart_sessions()
