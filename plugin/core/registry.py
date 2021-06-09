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


def get_position(view: sublime.View, event: Optional[dict] = None, point: Optional[int] = None) -> Optional[int]:
    if isinstance(point, int):
        return point
    if event:
        x, y = event.get("x"), event.get("y")
        if x is not None and y is not None:
            return view.window_to_text((x, y))
    try:
        return view.sel()[0].begin()
    except IndexError:
        return None


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
            position = get_position(self.view, event, point)
            if position is None:
                return False
            if not self.best_session(self.capability, position):
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

    def session_by_name(self, name: Optional[str] = None, capability_path: Optional[str] = None) -> Optional[Session]:
        target = name if name else self.session_name
        listener = windows.listener_for_view(self.view)
        if listener:
            for sv in listener.session_views_async():
                if sv.session.config.name == target:
                    if capability_path is None or sv.has_capability_async(capability_path):
                        return sv.session
                    else:
                        return None
        return None

    def sessions(self, capability: Optional[str] = None) -> Generator[Session, None, None]:
        yield from sessions_for_view(self.view, capability)


class LspRestartServerCommand(LspTextCommand):
    def run(self, edit: Any, config_name: str = None, show_quick_panel: bool = False) -> None:
        window = self.view.window()
        if not window:
            return
        self._config_names = [session.config.name for session in self.sessions()] if not config_name else [config_name]
        if not self._config_names:
            return
        if len(self._config_names) == 1:
            self.restart_server(0)
        else:
            self._config_names.insert(0, 'All Servers')
            if not show_quick_panel:
                self.restart_server(0)
            else:
                window.show_quick_panel(self._config_names, self.restart_server)

    def restart_server(self, index: int) -> None:
        if index > -1:

            def run_async() -> None:
                wm = windows.lookup(self.view.window())
                config_name = self._config_names[index]
                if not config_name or not self.session_by_name(config_name):
                    wm.restart_sessions_async()
                else:
                    wm.end_config_sessions_async(config_name)
                    wm.register_listener_async(wm.listener_for_view(self.view))  # type: ignore

            sublime.set_timeout_async(run_async)


class LspRecheckSessionsCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        sublime.set_timeout_async(lambda: windows.lookup(self.window).restart_sessions_async())
