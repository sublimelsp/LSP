import sublime
import sublime_plugin

from .core.protocol import Diagnostic, Point, Range
from .core.registry import windows
from .core.sessions import SessionBufferProtocol
from .core.typing import List, Dict, Tuple, Generator


def view_diagnostics(
    view: sublime.View
) -> Generator[Tuple[SessionBufferProtocol, List[Diagnostic]], None, None]:
    """XXX: Remove this function"""
    window = view.window()
    if window:
        manager = windows.lookup(window)
        listener = manager.listener_for_view(view)
        if listener:
            yield from listener.diagnostics_async()


def filter_by_point(
    file_diagnostics: Generator[Tuple[SessionBufferProtocol, List[Diagnostic]], None, None],
    point: Point
) -> Tuple[Dict[str, List[Diagnostic]], Range]:
    """XXX: Move this odd function to DocumentSyncListener"""
    diagnostics_by_config = {}
    extended_range = Range(point, point)
    for session_buffer, diagnostics in file_diagnostics:
        point_diagnostics = []
        for diagnostic in diagnostics:
            if diagnostic.range.contains(point):
                point_diagnostics.append(diagnostic)
                extended_range.extend(diagnostic.range)
        if point_diagnostics:
            diagnostics_by_config[session_buffer.session.config.name] = point_diagnostics
    return diagnostics_by_config, extended_range


def filter_by_range(
    file_diagnostics: Generator[Tuple[SessionBufferProtocol, List[Diagnostic]], None, None],
    rge: Range
) -> Tuple[Dict[str, List[Diagnostic]], Range]:
    """XXX: Move this odd function to DocumentSyncListener"""
    diagnostics_by_config = {}
    extended_range = Range(rge.start, rge.end)
    for session_buffer, diagnostics in file_diagnostics:
        intersecting_diagnostics = []
        for diagnostic in diagnostics:
            if diagnostic.range.intersects(rge):
                intersecting_diagnostics.append(diagnostic)
                extended_range.extend(diagnostic.range)
        if intersecting_diagnostics:
            diagnostics_by_config[session_buffer.session.config.name] = intersecting_diagnostics
    return diagnostics_by_config, extended_range


class LspNextDiagnosticCommand(sublime_plugin.WindowCommand):

    def run(self) -> None:
        sublime.set_timeout_async(self.run_async)

    def run_async(self) -> None:
        windows.lookup(self.window).select_next_diagnostic_async()


class LspPreviousDiagnosticCommand(sublime_plugin.WindowCommand):

    def run(self) -> None:
        sublime.set_timeout_async(self.run_async)

    def run_async(self) -> None:
        windows.lookup(self.window).select_previous_diagnostic_async()


class LspHideDiagnosticCommand(sublime_plugin.WindowCommand):

    def run(self) -> None:
        sublime.set_timeout_async(self.run_async)

    def run_async(self) -> None:
        windows.lookup(self.window).unselect_diagnostic_async()
