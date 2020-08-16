from .configurations import ConfigManager
from .sessions import Session
from .settings import client_configs
from .typing import Optional, Any, Generator, Iterable
from .windows import WindowManager
from .windows import WindowRegistry
import sublime
import sublime_plugin


class LSPViewEventListener(sublime_plugin.ViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        self._manager = None  # type: Optional[WindowManager]
        super().__init__(view)

    @classmethod
    def has_supported_syntax(cls, view_settings: dict) -> bool:
        syntax = view_settings.get('syntax')
        return bool(syntax and client_configs.is_syntax_supported(syntax))

    @property
    def manager(self) -> WindowManager:  # TODO: Return type is an Optional[WindowManager] !
        if not self._manager:
            window = self.view.window()
            if window:
                self._manager = windows.lookup(window)
        return self._manager  # type: ignore

    def has_manager(self) -> bool:
        return self._manager is not None

    def purge_changes_async(self) -> None:
        # Supermassive hack that will go away later.
        listeners = sublime_plugin.view_event_listeners.get(self.view.id(), [])
        for listener in listeners:
            if listener.__class__.__name__ == 'DocumentSyncListener':
                listener.purge_changes_async()  # type: ignore
                return

    def sessions(self, capability: Optional[str]) -> Generator[Session, None, None]:
        yield from self.manager.sessions(self.view, capability)

    def session(self, capability: str, point: Optional[int] = None) -> Optional[Session]:
        return _best_session(self.view, self.sessions(capability), point)


def sessions_for_view(view: sublime.View, capability: Optional[str] = None) -> Generator[Session, None, None]:
    """
    Returns all sessions for this view, optionally matching the capability path.
    """
    window = view.window()
    if window:
        manager = windows.lookup(window)
        yield from manager.sessions(view, capability)


def _best_session(view: sublime.View, sessions: Iterable[Session], point: Optional[int] = None) -> Optional[Session]:
    if point is None:
        try:
            point = view.sel()[0].b
        except IndexError:
            return None
    scope = view.scope_name(point)
    try:
        return max(sessions, key=lambda session: session.config.score_feature(scope))
    except ValueError:
        return None


configs = ConfigManager(client_configs.all)
client_configs.set_listener(configs.update)
windows = WindowRegistry(configs)


def get_position(view: sublime.View, event: Optional[dict] = None) -> int:
    if event:
        return view.window_to_text((event["x"], event["y"]))
    else:
        return view.sel()[0].begin()


class LspTextCommand(sublime_plugin.TextCommand):
    """
    Inherit from this class to define your requests that should be triggered via the command palette and/or a
    keybinding.
    """

    # When this is defined in a derived class, the command is enabled if and only if there exists a session attached
    # to the view that has the given capability. When both `capability` and `session_name` are defined, `capability`
    # wins.
    capability = ''

    # When this is defined in a derived class, the command is enabled if and only if there exists a session attached
    # to the view that has the given name. When both `capability` and `session_name` are defined, `capability` wins.
    session_name = ''

    def is_enabled(self, event: Optional[dict] = None) -> bool:
        if self.capability:
            # At least one active session with the given capability must exist.
            return bool(self.best_session(self.capability, get_position(self.view, event)))
        elif self.session_name:
            # There must exist an active session with the given (config) name.
            return bool(self.session_by_name(self.session_name))
        else:
            # Any session will do.
            return any(self.sessions())

    def want_event(self) -> bool:
        return True

    def best_session(self, capability: str, point: Optional[int] = None) -> Optional[Session]:
        return _best_session(self.view, self.sessions(capability), point)

    def session_by_name(self, name: Optional[str] = None) -> Optional[Session]:
        target = name if name else self.session_name
        for session in self.sessions():
            if session.config.name == target:
                return session
        return None

    def sessions(self, capability: Optional[str] = None) -> Generator[Session, None, None]:
        yield from sessions_for_view(self.view, capability)


class LspRestartClientCommand(sublime_plugin.TextCommand):
    def run(self, edit: Any) -> None:
        window = self.view.window()
        if window:
            windows.lookup(window).restart_sessions_async()


class LspEndSessionCommand(sublime_plugin.WindowCommand):
    def run(self, name: str) -> None:
        sublime.set_timeout_async(lambda: windows.lookup(self.window).end_config_sessions_async(name))


class LspRecheckSessionsCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        sublime.set_timeout_async(lambda: windows.lookup(self.window).restart_sessions_async())
