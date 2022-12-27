from .protocol import Diagnostic
from .protocol import Point
from .sessions import AbstractViewListener
from .sessions import Session
from .tree_view import TreeDataProvider
from .tree_view import TreeViewSheet
from .typing import Optional, Any, Generator, Iterable, List
from .views import first_selection_region
from .views import MissingUriError
from .views import point_to_offset
from .views import uri_from_view
from .windows import WindowManager
from .windows import WindowRegistry
from functools import partial
import operator
import sublime
import sublime_api  # pyright: ignore[reportMissingImports]
import sublime_plugin


windows = WindowRegistry()


def new_tree_view_sheet(
    window: sublime.Window,
    name: str,
    data_provider: TreeDataProvider,
    header: str = "",
    flags: int = 0,
    group: int = -1
) -> Optional[TreeViewSheet]:
    """
    Use this function to create a new TreeView in form of a special HtmlSheet (TreeViewSheet). Only one TreeViewSheet
    with the given name is allowed per window. If there already exists a TreeViewSheet with the same name, its content
    will be replaced with the new data. The header argument is allowed to contain minihtml markup.
    """
    wm = windows.lookup(window)
    if not wm:
        return None
    if name in wm.tree_view_sheets:
        tree_view_sheet = wm.tree_view_sheets[name]
        sheet_id = tree_view_sheet.id()
        if tree_view_sheet.window():
            tree_view_sheet.set_provider(data_provider, header)
            # add to selected sheets if not already selected
            selected_sheets = window.selected_sheets()
            for sheet in window.sheets():
                if isinstance(sheet, sublime.HtmlSheet) and sheet.id() == sheet_id:
                    if sheet not in selected_sheets:
                        selected_sheets.append(sheet)
                        window.select_sheets(selected_sheets)
                    break
            return tree_view_sheet
    tree_view_sheet = TreeViewSheet(
        sublime_api.window_new_html_sheet(window.window_id, name, "", flags, group),
        name,
        data_provider,
        header
    )
    wm.tree_view_sheets[name] = tree_view_sheet
    return tree_view_sheet


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

    def session(self) -> Optional[Session]:
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

    def session_by_name(self, session_name: str) -> Optional[Session]:
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

    @staticmethod
    def applies_to_context_menu(event: Optional[dict]) -> bool:
        return event is not None and 'x' in event

    def get_listener(self) -> Optional[AbstractViewListener]:
        return windows.listener_for_view(self.view)

    def best_session(self, capability: str, point: Optional[int] = None) -> Optional[Session]:
        listener = self.get_listener()
        return listener.session_async(capability, point) if listener else None

    def session_by_name(self, name: Optional[str] = None, capability_path: Optional[str] = None) -> Optional[Session]:
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

    def sessions(self, capability_path: Optional[str] = None) -> Generator[Session, None, None]:
        listener = self.get_listener()
        if listener:
            for sv in listener.session_views_async():
                if capability_path is None or sv.has_capability_async(capability_path):
                    yield sv.session


class LspRestartServerCommand(LspTextCommand):

    def run(self, edit: Any, config_name: Optional[str] = None) -> None:
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

    def restart_server(self, wm: WindowManager, index: int) -> None:
        if index == -1:
            return

        def run_async() -> None:
            config_name = self._config_names[index]
            if config_name:
                wm.restart_sessions_async(config_name)

        sublime.set_timeout_async(run_async)


class LspRecheckSessionsCommand(sublime_plugin.WindowCommand):
    def run(self, config_name: Optional[str] = None) -> None:

        def run_async() -> None:
            wm = windows.lookup(self.window)
            if wm:
                wm.restart_sessions_async(config_name)

        sublime.set_timeout_async(run_async)


def navigate_diagnostics(view: sublime.View, point: Optional[int], forward: bool = True) -> None:
    try:
        uri = uri_from_view(view)
    except MissingUriError:
        return
    wm = windows.lookup(view.window())
    if not wm:
        return
    diagnostics = []  # type: List[Diagnostic]
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
        diag_pos = point_to_offset(Point.from_lsp(diagnostic['range']['start']), view)
        if op_func(diag_pos, point):
            break
    else:
        diag_pos = point_to_offset(Point.from_lsp(diagnostics[0]['range']['start']), view)
    view.run_command('lsp_selection_set', {'regions': [(diag_pos, diag_pos)]})
    view.show_at_center(diag_pos)
    # We need a small delay before showing the popup to wait for the scrolling animation to finish. Otherwise ST would
    # immediately hide the popup.
    sublime.set_timeout_async(lambda: view.run_command('lsp_hover', {'only_diagnostics': True, 'point': diag_pos}), 200)


class LspNextDiagnosticCommand(LspTextCommand):

    def run(self, edit: sublime.Edit, point: Optional[int] = None) -> None:
        navigate_diagnostics(self.view, point, forward=True)


class LspPrevDiagnosticCommand(LspTextCommand):

    def run(self, edit: sublime.Edit, point: Optional[int] = None) -> None:
        navigate_diagnostics(self.view, point, forward=False)


class LspExpandTreeItemCommand(LspWindowCommand):

    capability = 'callHierarchyProvider'

    def run(self, name: str, id: str) -> None:
        wm = windows.lookup(self.window)
        if not wm:
            return
        sheet = wm.tree_view_sheets.get(name)
        if not sheet:
            return
        sheet.expand_item(id)


class LspCollapseTreeItemCommand(LspWindowCommand):

    capability = 'callHierarchyProvider'

    def run(self, name: str, id: str) -> None:
        wm = windows.lookup(self.window)
        if not wm:
            return
        sheet = wm.tree_view_sheets.get(name)
        if not sheet:
            return
        sheet.collapse_item(id)
