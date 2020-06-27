import html
import os
import re
import sublime
import sublime_plugin

from .core.diagnostics import DiagnosticsWalker, DiagnosticsUpdateWalk, DiagnosticsCursor, DocumentsState
from .core.logging import debug
from .core.panels import ensure_panel
from .core.protocol import Diagnostic, DiagnosticSeverity, DiagnosticRelatedInformation, Point, Range
from .core.registry import windows, LSPViewEventListener
from .core.settings import settings, PLUGIN_NAME
from .core.typing import List, Dict, Optional, Tuple
from .core.views import range_to_region, region_to_range


diagnostic_severity_names = {
    DiagnosticSeverity.Error: "error",
    DiagnosticSeverity.Warning: "warning",
    DiagnosticSeverity.Information: "info",
    DiagnosticSeverity.Hint: "hint"
}

diagnostic_severity_scopes = {
    DiagnosticSeverity.Error: 'markup.deleted.lsp sublimelinter.mark.error markup.error.lsp',
    DiagnosticSeverity.Warning: 'markup.changed.lsp sublimelinter.mark.warning markup.warning.lsp',
    DiagnosticSeverity.Information: 'markup.inserted.lsp sublimelinter.gutter-mark markup.info.lsp',
    DiagnosticSeverity.Hint: 'markup.inserted.lsp sublimelinter.gutter-mark markup.info.suggestion.lsp'
}

UNDERLINE_FLAGS = (sublime.DRAW_SQUIGGLY_UNDERLINE | sublime.DRAW_NO_OUTLINE | sublime.DRAW_NO_FILL |
                   sublime.DRAW_EMPTY_AS_OVERWRITE)

BOX_FLAGS = sublime.DRAW_NO_FILL | sublime.DRAW_EMPTY_AS_OVERWRITE


def is_same_file(file_path_a: str, file_path_b: str) -> bool:
    try:
        return os.path.samefile(file_path_a, file_path_b)
    except FileNotFoundError:
        return False


def format_severity(severity: int) -> str:
    return diagnostic_severity_names.get(severity, "???")


def view_diagnostics(view: sublime.View) -> Dict[str, List[Diagnostic]]:
    if view.window():
        file_name = view.file_name()
        if file_name:
            window = view.window()
            if window:
                window_diagnostics = windows.lookup(window).diagnostics.get()
                for file in window_diagnostics:
                    if is_same_file(file, file_name):
                        return window_diagnostics[file]
    return {}


def filter_by_point(file_diagnostics: Dict[str, List[Diagnostic]], point: Point) -> Dict[str, List[Diagnostic]]:
    diagnostics_by_config = {}
    for config_name, diagnostics in file_diagnostics.items():
        point_diagnostics = [
            diagnostic for diagnostic in diagnostics if diagnostic.range.contains(point)
        ]
        if point_diagnostics:
            diagnostics_by_config[config_name] = point_diagnostics
    return diagnostics_by_config


def filter_by_range(file_diagnostics: Dict[str, List[Diagnostic]], rge: Range) -> Dict[str, List[Diagnostic]]:
    diagnostics_by_config = {}
    for config_name, diagnostics in file_diagnostics.items():
        point_diagnostics = [
            diagnostic for diagnostic in diagnostics if diagnostic.range.intersects(rge)
        ]
        if point_diagnostics:
            diagnostics_by_config[config_name] = point_diagnostics
    return diagnostics_by_config


class DiagnosticsCursorListener(LSPViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.has_status = False

    @classmethod
    def is_applicable(cls, view_settings: dict) -> bool:
        return settings.show_diagnostics_in_view_status and cls.has_supported_syntax(view_settings)

    def on_selection_modified_async(self) -> None:
        selections = self.view.sel()
        if len(selections) > 0:
            file_path = self.view.file_name()
            if file_path:
                pos = selections[0].begin()
                region = self.view.line(pos)
                line_range = region_to_range(self.view, region)
                diagnostics = filter_by_range(self.manager.diagnostics.get_by_file(file_path), line_range)
                if diagnostics:
                    flattened = (d for sublist in diagnostics.values() for d in sublist)
                    first_diagnostic = next(flattened, None)
                    if first_diagnostic:
                        self.show_diagnostics_status(first_diagnostic)
                        return
            if self.has_status:
                self.clear_diagnostics_status()

    def show_diagnostics_status(self, diagnostic: Diagnostic) -> None:
        self.has_status = True
        # Because set_status eats newlines, newlines that aren't surrounded by any space
        # need to have some added, to stop words from becoming joined.
        spaced_message = re.sub(r'(\S)\n(\S)', r'\1 \2', diagnostic.message)
        self.view.set_status('lsp_diagnostics', spaced_message)

    def clear_diagnostics_status(self) -> None:
        self.view.erase_status('lsp_diagnostics')
        self.has_status = False


class LspClearDiagnosticsCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        windows.lookup(self.window).diagnostics.clear()


def ensure_diagnostics_panel(window: sublime.Window) -> Optional[sublime.View]:
    return ensure_panel(window, "diagnostics", r"^\s*\S\s+(\S.*):$", r"^\s+([0-9]+):?([0-9]+).*$",
                        "Packages/" + PLUGIN_NAME + "/Syntaxes/Diagnostics.sublime-syntax")


class LspNextDiagnosticCommand(sublime_plugin.WindowCommand):

    def run(self) -> None:
        windows.lookup(self.window).diagnostics.select_next()


class LspPreviousDiagnosticCommand(sublime_plugin.WindowCommand):

    def run(self) -> None:
        windows.lookup(self.window).diagnostics.select_previous()


class LspHideDiagnosticCommand(sublime_plugin.WindowCommand):

    def run(self) -> None:
        windows.lookup(self.window).diagnostics.select_none()


class DiagnosticsPhantoms(object):

    def __init__(self, window: sublime.Window) -> None:
        self._window = window
        self._last_phantom_set = None  # type: 'Optional[sublime.PhantomSet]'

    def set_diagnostic(self, file_diagnostic: Optional[Tuple[str, Diagnostic]]) -> None:
        self.clear()

        if file_diagnostic:
            file_path, diagnostic = file_diagnostic
            view = self._window.open_file(file_path, sublime.TRANSIENT)
            if view.is_loading():
                sublime.set_timeout(lambda: self.apply_phantom(view, diagnostic), 500)
            else:
                self.apply_phantom(view, diagnostic)
        else:
            if self._last_phantom_set:
                view = self._last_phantom_set.view
                has_phantom = view.settings().get('lsp_diagnostic_phantom')
                if not has_phantom:
                    view.settings().set('lsp_diagnostic_phantom', False)

    def apply_phantom(self, view: sublime.View, diagnostic: Diagnostic) -> None:
        phantom_set = sublime.PhantomSet(view, "lsp_diagnostics")
        phantom = self.create_phantom(view, diagnostic)
        phantom_set.update([phantom])
        view.show_at_center(phantom.region)
        self._last_phantom_set = phantom_set
        has_phantom = view.settings().get('lsp_diagnostic_phantom')
        if not has_phantom:
            view.settings().set('lsp_diagnostic_phantom', True)

    def create_phantom(self, view: sublime.View, diagnostic: Diagnostic) -> sublime.Phantom:
        region = range_to_region(diagnostic.range, view)
        line = "[{}] {}".format(diagnostic.source, diagnostic.message) if diagnostic.source else diagnostic.message
        message = "<p>" + "<br>".join(html.escape(line, quote=False) for line in line.splitlines()) + "</p>"

        additional_infos = "<br>".join([self.format_diagnostic_related_info(info) for info in diagnostic.related_info])
        severity = "error" if diagnostic.severity == DiagnosticSeverity.Error else "warning"
        content = message + "<p class='additional'>" + additional_infos + "</p>" if additional_infos else message
        markup = self.create_phantom_html(content, severity)
        return sublime.Phantom(
            region,
            markup,
            sublime.LAYOUT_BELOW,
            self.navigate
        )

    # TODO: share with hover?
    def format_diagnostic_related_info(self, info: DiagnosticRelatedInformation) -> str:
        file_path = info.location.file_path
        base_dir = windows.lookup(self._window).get_project_path(file_path)
        if base_dir:
            file_path = os.path.relpath(file_path, base_dir)
        location = "{}:{}:{}".format(info.location.file_path, info.location.range.start.row + 1,
                                     info.location.range.start.col + 1)
        return "<a href='location:{}'>{}</a>: {}".format(location, location, html.escape(info.message))

    def navigate(self, href: str) -> None:
        if href == "hide":
            self.clear()
        elif href == "next":
            self._window.run_command("lsp_next_diagnostic")
        elif href == "previous":
            self._window.run_command("lsp_previous_diagnostic")
        elif href.startswith("location"):
            # todo: share with hover?
            _, file_path, location = href.split(":", 2)
            self._window.open_file(file_path + ":" + location, sublime.ENCODED_POSITION | sublime.TRANSIENT)

    def create_phantom_html(self, content: str, severity: str) -> str:
        stylesheet = sublime.load_resource("Packages/LSP/phantoms.css")
        return """<body id=inline-error>
                    <style>{}</style>
                    <div class="{}-arrow"></div>
                    <div class="{} container">
                        <div class="toolbar">
                            <a href="hide">×</a>
                            <a href="previous">↑</a>
                            <a href="next">↓</a>
                        </div>
                        <div class="content">{}</div>
                    </div>
                </body>""".format(stylesheet, severity, severity, content)

    def clear(self) -> None:
        if self._last_phantom_set:
            self._last_phantom_set.view.settings().set('lsp_diagnostic_phantom', False)
            self._last_phantom_set.update([])


class DiagnosticViewRegions(DiagnosticsUpdateWalk):

    def __init__(self, view: sublime.View) -> None:
        self._view = view
        self._regions = {}  # type: Dict[int, List[sublime.Region]]
        self._relevant_file = False

    def begin(self) -> None:
        for severity in self._regions:
            self._regions[severity] = []

    def begin_file(self, file_name: str) -> None:
        # TODO: would be nice if walk could skip this updater
        file = self._view.file_name()
        if file and is_same_file(file_name, file):
            self._relevant_file = True

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        if self._relevant_file:
            self._regions.setdefault(diagnostic.severity, []).append(range_to_region(diagnostic.range, self._view))

    def end_file(self, file_name: str) -> None:
        self._relevant_file = False

    def end(self) -> None:
        for severity in reversed(range(settings.show_diagnostics_severity_level + 1)):
            region_name = "lsp_" + format_severity(severity)
            if severity in self._regions:
                regions = self._regions[severity]
                scope_name = diagnostic_severity_scopes[severity]
                if settings.diagnostics_gutter_marker == "sign":
                    diagnostic_severity_icons = {
                        DiagnosticSeverity.Error: "Packages/LSP/icons/error.png",
                        DiagnosticSeverity.Warning: "Packages/LSP/icons/warning.png",
                        DiagnosticSeverity.Information: "Packages/LSP/icons/info.png",
                        DiagnosticSeverity.Hint: "Packages/LSP/icons/info.png"
                    }
                    icon = diagnostic_severity_icons[severity]
                else:
                    icon = settings.diagnostics_gutter_marker
                self._view.add_regions(
                    region_name, regions, scope_name, icon,
                    UNDERLINE_FLAGS if settings.diagnostics_highlight_style == "underline" else BOX_FLAGS)
            else:
                self._view.erase_regions(region_name)


class HasRelevantDiagnostics(DiagnosticsUpdateWalk):
    def __init__(self) -> None:
        self.result = False

    def begin(self) -> None:
        self.result = False

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        if diagnostic.severity <= settings.auto_show_diagnostics_panel_level:
            self.result = True


class StatusBarSummary(DiagnosticsUpdateWalk):
    def __init__(self, window: sublime.Window) -> None:
        self._window = window

    def begin(self) -> None:
        self._errors = 0
        self._warnings = 0

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        if diagnostic.severity == DiagnosticSeverity.Error:
            self._errors += 1
        elif diagnostic.severity == DiagnosticSeverity.Warning:
            self._warnings += 1

    def end(self) -> None:
        if self._errors > 0 or self._warnings > 0:
            count = 'E: {} W: {}'.format(self._errors, self._warnings)
        else:
            count = ""

        # todo: make a sticky status on active view.
        active_view = self._window.active_view()
        if active_view:
            active_view.set_status('lsp_errors_warning_count', count)


class DiagnosticOutputPanel(DiagnosticsUpdateWalk):
    def __init__(self, window: sublime.Window) -> None:
        self._window = window
        self._to_render = []  # type: List[str]
        self._panel = ensure_diagnostics_panel(self._window)

    def begin(self) -> None:
        self._to_render = []
        self._file_content = ""

    def begin_file(self, file_path: str) -> None:
        self._base_dir = windows.lookup(self._window).get_project_path(file_path)
        self._file_content = ""

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        if diagnostic.severity <= settings.show_diagnostics_severity_level:
            item = self.format_diagnostic(diagnostic)
            self._file_content += item + "\n"

    def end_file(self, file_path: str) -> None:
        if self._file_content:
            panel_file_path = os.path.relpath(file_path, self._base_dir) if self._base_dir else file_path
            self._to_render.append(" ◌ {}:\n{}".format(panel_file_path, self._file_content))

    def end(self) -> None:
        assert self._panel, "must have a panel now!"
        self._panel.settings().set("result_base_dir", self._base_dir)
        self._panel.run_command("lsp_update_panel", {"characters": "\n".join(self._to_render)})

    def format_diagnostic(self, diagnostic: Diagnostic) -> str:
        location = "{:>8}:{:<4}".format(
            diagnostic.range.start.row + 1, diagnostic.range.start.col + 1)
        lines = diagnostic.message.splitlines() or [""]
        formatted = " {}\t{:<12}\t{:<10}\t{}".format(
            location, diagnostic.source, format_severity(diagnostic.severity), lines[0])
        for line in lines[1:]:
            formatted = formatted + "\n {:<12}\t{:<12}\t{:<10}\t{}".format("", "", "", line)
        return formatted


class DiagnosticsPresenter(object):

    def __init__(self, window: sublime.Window, documents_state: DocumentsState) -> None:
        self._window = window
        self._dirty = False
        self._received_diagnostics_after_change = False
        self._show_panel_on_diagnostics = False if settings.auto_show_diagnostics_panel == 'never' else True
        self._panel_update = DiagnosticOutputPanel(self._window)
        self._bar_summary_update = StatusBarSummary(self._window)
        self._relevance_check = HasRelevantDiagnostics()
        self._cursor = DiagnosticsCursor(settings.show_diagnostics_severity_level)
        self._phantoms = DiagnosticsPhantoms(self._window)
        self._diagnostics = {}  # type: Dict[str, Dict[str, List[Diagnostic]]]
        if settings.auto_show_diagnostics_panel == 'saved':
            setattr(documents_state, 'changed', self.on_document_changed)
            setattr(documents_state, 'saved', self.on_document_saved)

    def on_document_changed(self) -> None:
        self._received_diagnostics_after_change = False

    def on_document_saved(self) -> None:
        if self._received_diagnostics_after_change:
            self.show_panel_if_relevant()
        else:
            self._show_panel_on_diagnostics = True

    def show_panel_if_relevant(self) -> None:
        self._show_panel_on_diagnostics = False

        if self._relevance_check.result:
            self._window.run_command("show_panel", {"panel": "output.diagnostics"})
        else:
            self._window.run_command("hide_panel", {"panel": "output.diagnostics"})

    def update(self, file_path: str, config_name: str, diagnostics: Dict[str, Dict[str, List[Diagnostic]]]) -> None:
        self._diagnostics = diagnostics
        self._received_diagnostics_after_change = True

        if not self._window.is_valid():
            debug('ignoring update to closed window')
            return

        updatables = [self._panel_update, self._relevance_check]
        if settings.show_diagnostics_count_in_view_status:
            updatables.append(self._bar_summary_update)

        view = self._window.find_open_file(file_path)
        if view and view.is_valid():
            view_region_updater = DiagnosticViewRegions(view)
            updatables.append(view_region_updater)
        else:
            debug('view not found for', file_path)

        if self._cursor.has_value:
            updatables.append(self._cursor.update())

        walker = DiagnosticsWalker(updatables)
        walker.walk(diagnostics)

        if settings.auto_show_diagnostics_panel == 'always' or self._show_panel_on_diagnostics:
            self.show_panel_if_relevant()

    def select(self, direction: int) -> None:
        file_path = None  # type: Optional[str]
        point = None  # type: Optional[Point]

        if not self._cursor.has_value:
            active_view = self._window.active_view()
            if active_view:
                file_path = active_view.file_name()
                point = Point(*active_view.rowcol(active_view.sel()[0].begin()))

        walk = self._cursor.from_diagnostic(direction) if self._cursor.has_value else self._cursor.from_position(
            direction, file_path, point)
        walker = DiagnosticsWalker([walk])
        walker.walk(self._diagnostics)
        self._phantoms.set_diagnostic(self._cursor.value)

    def deselect(self) -> None:
        self._phantoms.set_diagnostic(None)
