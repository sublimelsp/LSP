import html
import os
import re
import sublime
import sublime_plugin

from .core.diagnostics import DiagnosticsWalker, DiagnosticsUpdateWalk, DiagnosticsCursor
from .core.logging import debug
from .core.panels import ensure_panel
from .core.protocol import DiagnosticSeverity, Diagnostic, DiagnosticRelatedInformation, Point, Range
from .core.registry import windows, LSPViewEventListener
from .core.settings import settings, PLUGIN_NAME
from .core.typing import List, Dict, Optional, Tuple
from .core.views import range_to_region
from .core.views import region_to_range
from .core.views import DIAGNOSTIC_SEVERITY


def view_diagnostics(view: sublime.View) -> Dict[str, List[Diagnostic]]:
    window = view.window()
    if window:
        manager = windows.lookup(window)
        listener = manager.listener_for_view(view)
        if listener:
            return listener.diagnostics_async()
    return {}


def filter_by_point(
    file_diagnostics: Dict[str, List[Diagnostic]],
    point: Point
) -> Tuple[Dict[str, List[Diagnostic]], Range]:
    diagnostics_by_config = {}
    extended_range = Range(point, point)
    for config_name, diagnostics in file_diagnostics.items():
        point_diagnostics = []
        for diagnostic in diagnostics:
            if diagnostic.range.contains(point):
                point_diagnostics.append(diagnostic)
                extended_range.extend(diagnostic.range)
        if point_diagnostics:
            diagnostics_by_config[config_name] = point_diagnostics
    return (diagnostics_by_config, extended_range)


def filter_by_range(
    file_diagnostics: Dict[str, List[Diagnostic]],
    rge: Range
) -> Tuple[Dict[str, List[Diagnostic]], Range]:
    diagnostics_by_config = {}
    extended_range = Range(rge.start, rge.end)
    for config_name, diagnostics in file_diagnostics.items():
        intersecting_diagnostics = []
        for diagnostic in diagnostics:
            if diagnostic.range.intersects(rge):
                intersecting_diagnostics.append(diagnostic)
                extended_range.extend(diagnostic.range)
        if intersecting_diagnostics:
            diagnostics_by_config[config_name] = intersecting_diagnostics
    return (diagnostics_by_config, extended_range)


class LspClearDiagnosticsCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        sublime.set_timeout_async(self.run_async)

    def run_async(self) -> None:
        windows.lookup(self.window).clear_diagnostics_async()


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
