from .configurations import ConfigManager
from .sessions import Session
from .settings import client_configs
from .typing import Optional, Any, Generator, Iterable
from .windows import WindowRegistry
import sublime
import sublime_plugin


def sessions_for_view(view: sublime.View, capability: Optional[str] = None) -> Generator[Session, None, None]:
    """
    Returns all sessions for this view, optionally matching the capability path.
    """
    window = view.window()
    if window:
        manager = windows.lookup(window)
        yield from manager.sessions(view, capability)


def best_session(view: sublime.View, sessions: Iterable[Session], point: Optional[int] = None) -> Optional[Session]:
    if point is None:
        try:
            point = view.sel()[0].b
        except IndexError:
            return None
    try:
        return max(sessions, key=lambda s: view.score_selector(point, s.config.priority_selector))  # type: ignore
    except ValueError:
        return None


configs = ConfigManager(client_configs.all)
client_configs.set_listener(configs.update)
windows = WindowRegistry(configs)


def get_position(view: sublime.View, event: Optional[dict] = None, point: Optional[int] = None) -> int:
    if isinstance(point, int):
        return point
    elif event:
        return view.window_to_text((event["x"], event["y"]))
    else:
        return view.sel()[0].begin()


class LspTextCommand(sublime_plugin.TextCommand):
    """
    Inherit from this class to define your requests that should be triggered via the command palette and/or a
    keybinding.
    """

    # When this is defined in a derived class, the command is enabled only if there exists a session attached to the
    # view that has the given capability.
    capability = ''

    # When this is defined in a derived class, the command is enabled only if there exists a session attached to the
    # view that has the given name.
    session_name = ''

    def is_enabled(self, event: Optional[dict] = None, point: Optional[int] = None) -> bool:
        if self.capability:
            # At least one active session with the given capability must exist.
            if not self.best_session(self.capability, get_position(self.view, event, point)):
                return False
        if self.session_name:
            # There must exist an active session with the given (config) name.
            if not self.session_by_name(self.session_name):
                return False
        if not self.capability and not self.session_name:
            # Any session will do.
            return any(self.sessions())
        return True

    def want_event(self) -> bool:
        return True

    def best_session(self, capability: str, point: Optional[int] = None) -> Optional[Session]:
        listener = windows.listener_for_view(self.view)
        return listener.session(capability, point) if listener else None

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


class LspRecheckSessionsCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        sublime.set_timeout_async(lambda: windows.lookup(self.window).restart_sessions_async())
