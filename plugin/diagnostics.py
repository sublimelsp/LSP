import html
import os
import sublime
import sublime_plugin

from .core.configurations import is_supported_syntax
from .core.logging import debug
from .core.panels import ensure_panel
from .core.protocol import Diagnostic, DiagnosticSeverity, Point, Range
from .core.settings import settings, PLUGIN_NAME, client_configs
from .core.views import range_to_region, region_to_range
from .core.registry import windows
from .core.windows import WindowManager

MYPY = False
if MYPY:
    from typing import Any, List, Dict, Callable, Optional
    from typing_extensions import Protocol
    assert Any and List and Dict and Callable and Optional
else:
    Protocol = object  # type: ignore


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

stylesheet = '''
            <style>
                div.error-arrow {
                    border-top: 0.4rem solid transparent;
                    border-left: 0.5rem solid color(var(--redish) blend(var(--background) 30%));
                    width: 0;
                    height: 0;
                }
                div.error {
                    padding: 0.4rem 0 0.4rem 0.7rem;
                    margin: 0 0 0.2rem;
                    border-radius: 0 0.2rem 0.2rem 0.2rem;
                }

                div.error span.message {
                    padding-right: 0.7rem;
                }

                div.error a {
                    text-decoration: inherit;
                    padding: 0.35rem 0.7rem 0.45rem 0.8rem;
                    position: relative;
                    bottom: 0.05rem;
                    border-radius: 0 0.2rem 0.2rem 0;
                    font-weight: bold;
                }
                html.dark div.error a {
                    background-color: #00000018;
                }
                html.light div.error a {
                    background-color: #ffffff18;
                }
            </style>
        '''

UNDERLINE_FLAGS = (sublime.DRAW_SQUIGGLY_UNDERLINE | sublime.DRAW_NO_OUTLINE | sublime.DRAW_NO_FILL |
                   sublime.DRAW_EMPTY_AS_OVERWRITE)

BOX_FLAGS = sublime.DRAW_NO_FILL | sublime.DRAW_EMPTY_AS_OVERWRITE


def create_phantom_html(text: str) -> str:
    global stylesheet
    formatted = "<br>".join(html.escape(line, quote=False) for line in text.splitlines())
    return """<body id=inline-error>{}
                <div class="error-arrow"></div>
                <div class="error">
                    <span class="message">{}</span>
                    <a href="code-actions">Code Actions</a>
                </div>
                </body>""".format(stylesheet, formatted)


def on_phantom_navigate(view: sublime.View, href: str, point: int) -> None:
    # TODO: don't mess with the user's cursor.
    sel = view.sel()
    sel.clear()
    sel.add(sublime.Region(point))
    view.run_command("lsp_code_actions")


def create_phantom(view: sublime.View, diagnostic: Diagnostic) -> sublime.Phantom:
    region = range_to_region(diagnostic.range, view)
    # TODO: hook up hide phantom (if keeping them)
    content = create_phantom_html(diagnostic.message)
    return sublime.Phantom(
        region,
        '<p>' + content + '</p>',
        sublime.LAYOUT_BELOW,
        lambda href: on_phantom_navigate(view, href, region.begin())
    )


def format_severity(severity: int) -> str:
    return diagnostic_severity_names.get(severity, "???")


def view_diagnostics(view: sublime.View) -> 'Dict[str, List[Diagnostic]]':
    if view.window():
        file_name = view.file_name()
        if file_name:
            window_diagnostics = windows.lookup(view.window())._diagnostics.get()
            return window_diagnostics.get(file_name, {})
    return {}


def filter_by_point(file_diagnostics: 'Dict[str, List[Diagnostic]]', point: Point) -> 'Dict[str, List[Diagnostic]]':
    diagnostics_by_config = {}
    for config_name, diagnostics in file_diagnostics.items():
        point_diagnostics = [
            diagnostic for diagnostic in diagnostics if diagnostic.range.contains(point)
        ]
        if point_diagnostics:
            diagnostics_by_config[config_name] = point_diagnostics
    return diagnostics_by_config


def filter_by_range(file_diagnostics: 'Dict[str, List[Diagnostic]]', rge: Range) -> 'Dict[str, List[Diagnostic]]':
    diagnostics_by_config = {}
    for config_name, diagnostics in file_diagnostics.items():
        point_diagnostics = [
            diagnostic for diagnostic in diagnostics if diagnostic.range.intersects(rge)
        ]
        if point_diagnostics:
            diagnostics_by_config[config_name] = point_diagnostics
    return diagnostics_by_config


def get_window_diagnostics(window: sublime.Window) -> 'Dict[str, Dict[str, List[Diagnostic]]]':
    return windows.lookup(window)._diagnostics.get()


class DiagnosticsCursorListener(sublime_plugin.ViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        self.view = view
        self.has_status = False

    @classmethod
    def is_applicable(cls, view_settings: dict) -> bool:
        if not settings.show_diagnostics_in_view_status:
            return False
        syntax = view_settings.get('syntax')
        if syntax:
            return is_supported_syntax(syntax, client_configs.all)
        else:
            return False

    def on_selection_modified_async(self) -> None:
        selections = self.view.sel()
        if len(selections) > 0:
            pos = selections[0].begin()
            region = self.view.line(pos)
            line_range = region_to_range(self.view, region)
            diagnostics_by_config = filter_by_range(view_diagnostics(self.view), line_range)
            if diagnostics_by_config:
                flattened = (d for sublist in diagnostics_by_config.values() for d in sublist)
                first_diagnostic = next(flattened, None)
                if first_diagnostic:
                    self.show_diagnostics_status(first_diagnostic)
            elif self.has_status:
                self.clear_diagnostics_status()

    def show_diagnostics_status(self, diagnostic: 'Diagnostic') -> None:
        self.has_status = True
        self.view.set_status('lsp_diagnostics', diagnostic.message)

    def clear_diagnostics_status(self) -> None:
        self.view.erase_status('lsp_diagnostics')
        self.has_status = False


class LspShowDiagnosticsPanelCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        ensure_diagnostics_panel(self.window)
        active_panel = self.window.active_panel()
        is_active_panel = (active_panel == "output.diagnostics")

        if is_active_panel:
            self.window.run_command("hide_panel", {"panel": "output.diagnostics"})
        else:
            self.window.run_command("show_panel", {"panel": "output.diagnostics"})


class LspClearDiagnosticsCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        windows.lookup(self.window)._diagnostics.clear()


def ensure_diagnostics_panel(window: sublime.Window) -> 'Optional[sublime.View]':
    return ensure_panel(window, "diagnostics", r"^\s*\S\s+(\S.*):$", r"^\s+([0-9]+):?([0-9]+).*$",
                        "Packages/" + PLUGIN_NAME + "/Syntaxes/Diagnostics.sublime-syntax")


class DocumentsState(Protocol):

    def changed(self) -> None:
        ...

    def saved(self) -> None:
        ...


class DiagnosticsUpdateWalk(object):

    def begin(self) -> None:
        pass

    def begin_file(self, file_path: str) -> None:
        pass

    def diagnostic(self, diagnostic: 'Diagnostic') -> None:
        pass

    def end_file(self, file_path: str) -> None:
        pass

    def end(self) -> None:
        pass


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
        if file_name == self._view.file_name():
            self._relevant_file = True

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        if self._relevant_file:
            if diagnostic.severity <= settings.show_diagnostics_severity_level:
                self._regions.setdefault(diagnostic.severity, []).append(range_to_region(diagnostic.range, self._view))

    def end_file(self, file_name: str) -> None:
        self._relevant_file = False

    def end(self) -> None:
        for severity in range(DiagnosticSeverity.Error, settings.show_diagnostics_severity_level):
            region_name = "lsp_" + format_severity(severity)
            if severity in self._regions:
                regions = self._regions[severity]
                scope_name = diagnostic_severity_scopes[severity]
                self._view.add_regions(
                    region_name, regions, scope_name, settings.diagnostics_gutter_marker,
                    UNDERLINE_FLAGS if settings.diagnostics_highlight_style == "underline" else BOX_FLAGS)
            else:
                self._view.erase_regions(region_name)


class DiagnosticsWalker(object):
    """ Iterate over diagnostics structure"""

    def __init__(self, subs: 'List[DiagnosticsUpdateWalk]') -> None:
        self._subscribers = subs

    def walk(self, diagnostics_by_file: 'Dict[str, Dict[str, List[Diagnostic]]]') -> None:
        self.invoke_each(lambda w: w.begin())

        if diagnostics_by_file:
            for file_path, source_diagnostics in diagnostics_by_file.items():

                self.invoke_each(lambda w: w.begin_file(file_path))

                for origin, diagnostics in source_diagnostics.items():
                    for diagnostic in diagnostics:
                        self.invoke_each(lambda w: w.diagnostic(diagnostic))

                self.invoke_each(lambda w: w.end_file(file_path))

        self.invoke_each(lambda w: w.end())

    def invoke_each(self, func: 'Callable[[DiagnosticsUpdateWalk], None]') -> None:
        for sub in self._subscribers:
            func(sub)


class HasRelevantDiagnostics(DiagnosticsUpdateWalk):

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
        self._base_dir = windows.lookup(self._window).get_project_path()
        self._to_render = []
        self._file_content = ""

    def begin_file(self, file_path: str) -> None:
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
        self._panel.set_read_only(False)
        self._panel.run_command("lsp_update_panel", {"characters": "\n".join(self._to_render)})
        self._panel.set_read_only(True)

    def format_diagnostic(self, diagnostic: Diagnostic) -> str:
        location = "{:>8}:{:<4}".format(
            diagnostic.range.start.row + 1, diagnostic.range.start.col + 1)
        lines = diagnostic.message.splitlines()
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
        self._show_panel_on_diagnostics = True
        self._panel_update = DiagnosticOutputPanel(self._window)
        self._bar_summary_update = StatusBarSummary(self._window)
        self._relevance_check = HasRelevantDiagnostics()
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

        # todo: worth checking before showing/hiding?
        # active_panel = window.active_panel()
        # is_active_panel = (active_panel == "output.diagnostics")

        if self._relevance_check.result:
            self._window.run_command("show_panel", {"panel": "output.diagnostics"})
        else:
            self._window.run_command("hide_panel", {"panel": "output.diagnostics"})

    def update(self, file_path: str, config_name: str) -> None:
        self._received_diagnostics_after_change = True

        if not self._window.is_valid():
            debug('ignoring update to closed window')
            return

        # todo: improve relation with storage
        diagnostics = get_window_diagnostics(self._window)
        updatables = [self._panel_update, self._relevance_check]

        if settings.show_diagnostics_count_in_view_status:
            updatables.append(self._bar_summary_update)

        view = self._window.find_open_file(file_path)
        if view and view.is_valid():
            view_region_updater = DiagnosticViewRegions(view)
            updatables.append(view_region_updater)
        else:
            debug('view not found for', file_path)

        walker = DiagnosticsWalker(updatables)
        walker.walk(diagnostics)

        if self._show_panel_on_diagnostics:
            self.show_panel_if_relevant()
