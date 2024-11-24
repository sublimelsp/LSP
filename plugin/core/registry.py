from __future__ import annotations
from .protocol import Diagnostic
from .protocol import Location
from .protocol import LocationLink
from .sessions import AbstractViewListener
from .sessions import Session
from .views import first_selection_region
from .views import get_uri_and_position_from_location
from .views import MissingUriError
from .views import position_to_offset
from .views import uri_from_view
from .windows import WindowManager
from .windows import WindowRegistry
from functools import partial
from typing import Any, Generator, Iterable
import operator
import sublime
import sublime_plugin


windows = WindowRegistry()


def best_session(view: sublime.View, sessions: Iterable[Session], point: int | None = None) -> Session | None:
    if point is None:
        try:
            point = view.sel()[0].b
        except IndexError:
            return None
    try:
        return max(sessions, key=lambda s: view.score_selector(point, s.config.priority_selector))
    except ValueError:
        return None


def get_position(view: sublime.View, event: dict | None = None, point: int | None = None) -> int | None:
    if isinstance(point, int):
        return point
    if event:
        x, y = event.get("x"), event.get("y")
        if x is not None and y is not None:
            return view.window_to_text((x, y))
    try:
        return view.sel()[0].b
    except IndexError:
        return None


class LspWindowCommand(sublime_plugin.WindowCommand):
    """
    Inherit from this class to define requests which are not bound to a particular view. This allows to run requests
    for example from links in HtmlSheets or when an unrelated file has focus.
    """

    # When this is defined in a derived class, the command is enabled only if there exists a session with the given
    # capability attached to a view in the window.
    capability = ''

    # When this is defined in a derived class, the command is enabled only if there exists a session with the given
    # name attached to a view in the window.
    session_name = ''

    def is_enabled(self) -> bool:
        return self.session() is not None

    def session(self) -> Session | None:
        wm = windows.lookup(self.window)
        if not wm:
            return None
        for session in wm.get_sessions():
            if self.capability and not session.has_capability(self.capability):
                continue
            if self.session_name and session.config.name != self.session_name:
                continue
            return session
        else:
            return None

    def sessions(self) -> Generator[Session, None, None]:
        wm = windows.lookup(self.window)
        if not wm:
            return None
        for session in wm.get_sessions():
            if self.capability and not session.has_capability(self.capability):
                continue
            if self.session_name and session.config.name != self.session_name:
                continue
            yield session

    def session_by_name(self, session_name: str) -> Session | None:
        wm = windows.lookup(self.window)
        if not wm:
            return None
        for session in wm.get_sessions():
            if self.capability and not session.has_capability(self.capability):
                continue
            if session.config.name == session_name:
                return session
        else:
            return None


class LspTextCommand(sublime_plugin.TextCommand):
    """
    Inherit from this class to define your requests that should be triggered via the command palette and/or a
    keybinding.
    """

    # When this is defined in a derived class, the command is enabled only if there exists a session with the given
    # capability attached to the active view.
    capability = ''

    # When this is defined in a derived class, the command is enabled only if there exists a session with the given
    # name attached to the active view.
    session_name = ''

    def is_enabled(self, event: dict | None = None, point: int | None = None) -> bool:
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

    @staticmethod
    def applies_to_context_menu(event: dict | None) -> bool:
        return event is not None and 'x' in event

    def get_listener(self) -> AbstractViewListener | None:
        return windows.listener_for_view(self.view)

    def best_session(self, capability: str, point: int | None = None) -> Session | None:
        listener = self.get_listener()
        return listener.session_async(capability, point) if listener else None

    def session_by_name(self, name: str | None = None, capability_path: str | None = None) -> Session | None:
        target = name if name else self.session_name
        listener = self.get_listener()
        if listener:
            for sv in listener.session_views_async():
                if sv.session.config.name == target:
                    if capability_path is None or sv.has_capability_async(capability_path):
                        return sv.session
                    else:
                        return None
        return None

    def sessions(self, capability_path: str | None = None) -> Generator[Session, None, None]:
        listener = self.get_listener()
        if listener:
            for sv in listener.session_views_async():
                if capability_path is None or sv.has_capability_async(capability_path):
                    yield sv.session


class LspOpenLocationCommand(LspWindowCommand):
    """
    A command to be used by third-party ST packages that need to open an URI with some abstract scheme.
    """

    def run(
        self,
        location: Location | LocationLink,
        session_name: str | None = None,
        flags: sublime.NewFileFlags = sublime.NewFileFlags.NONE,
        group: int = -1,
        event: dict | None = None
    ) -> None:
        if event:
            modifier_keys = event.get('modifier_keys')
            if modifier_keys:
                if 'primary' in modifier_keys:
                    flags |= sublime.NewFileFlags.ADD_TO_SELECTION | sublime.NewFileFlags.SEMI_TRANSIENT | sublime.NewFileFlags.CLEAR_TO_RIGHT  # noqa: E501
                elif 'shift' in modifier_keys:
                    flags |= sublime.NewFileFlags.ADD_TO_SELECTION | sublime.NewFileFlags.SEMI_TRANSIENT
        sublime.set_timeout_async(lambda: self._run_async(location, session_name, flags, group))

    def want_event(self) -> bool:
        return True

    def _run_async(
        self, location: Location | LocationLink, session_name: str | None, flags: sublime.NewFileFlags, group: int
    ) -> None:
        session = self.session_by_name(session_name) if session_name else self.session()
        if session:
            session.open_location_async(location, flags, group) \
                .then(lambda view: self._handle_continuation(location, view is not None))

    def _handle_continuation(self, location: Location | LocationLink, success: bool) -> None:
        if not success:
            uri, _ = get_uri_and_position_from_location(location)
            message = f"Failed to open {uri}"
            sublime.status_message(message)


class LspRestartServerCommand(LspTextCommand):

    def run(self, edit: Any, config_name: str | None = None) -> None:
        wm = windows.lookup(self.view.window())
        if not wm:
            return
        self._config_names = [session.config.name for session in self.sessions()] if not config_name else [config_name]
        if not self._config_names:
            return
        if len(self._config_names) == 1:
            self.restart_server(wm, 0)
        else:
            wm.window.show_quick_panel(self._config_names, partial(self.restart_server, wm))

    def want_event(self) -> bool:
        return False

    def restart_server(self, wm: WindowManager, index: int) -> None:
        if index == -1:
            return

        def run_async() -> None:
            config_name = self._config_names[index]
            if config_name:
                wm.restart_sessions_async(config_name)

        sublime.set_timeout_async(run_async)


def navigate_diagnostics(view: sublime.View, point: int | None, forward: bool = True) -> None:
    try:
        uri = uri_from_view(view)
    except MissingUriError:
        return
    wm = windows.lookup(view.window())
    if not wm:
        return
    diagnostics: list[Diagnostic] = []
    for session in wm.get_sessions():
        diagnostics.extend(session.diagnostics.diagnostics_by_document_uri(uri))
    if not diagnostics:
        return
    # Sort diagnostics by location
    diagnostics.sort(key=lambda d: operator.itemgetter('line', 'character')(d['range']['start']), reverse=not forward)
    if point is None:
        region = first_selection_region(view)
        point = region.b if region is not None else 0
    # Find next/previous diagnostic or wrap around and jump to the first/last one, if there are no more diagnostics in
    # this view after/before the cursor
    op_func = operator.gt if forward else operator.lt
    for diagnostic in diagnostics:
        diag_pos = position_to_offset(diagnostic['range']['start'], view)
        if op_func(diag_pos, point):
            break
    else:
        diag_pos = position_to_offset(diagnostics[0]['range']['start'], view)
    view.run_command('lsp_selection_set', {'regions': [(diag_pos, diag_pos)]})
    view.show_at_center(diag_pos)
    # We need a small delay before showing the popup to wait for the scrolling animation to finish. Otherwise ST would
    # immediately hide the popup.
    sublime.set_timeout_async(lambda: view.run_command('lsp_hover', {'only_diagnostics': True, 'point': diag_pos}), 200)


class LspNextDiagnosticCommand(LspTextCommand):

    def run(self, edit: sublime.Edit, point: int | None = None) -> None:
        navigate_diagnostics(self.view, point, forward=True)

    def want_event(self) -> bool:
        return False


class LspPrevDiagnosticCommand(LspTextCommand):

    def run(self, edit: sublime.Edit, point: int | None = None) -> None:
        navigate_diagnostics(self.view, point, forward=False)

    def want_event(self) -> bool:
        return False
