import html
import os
import sublime
import sublime_plugin

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass

from .core.configurations import is_supported_syntax
from .core.diagnostics import (
    DiagnosticsUpdate
)
from .core.events import global_events
from .core.logging import debug
from .core.panels import ensure_panel
from .core.protocol import Diagnostic, DiagnosticSeverity
from .core.settings import settings, PLUGIN_NAME, client_configs
from .core.views import range_to_region
from .core.registry import windows


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


def on_phantom_navigate(view: sublime.View, href: str, point: int):
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


def format_diagnostic(diagnostic: Diagnostic) -> str:
    location = "{:>8}:{:<4}".format(
        diagnostic.range.start.row + 1, diagnostic.range.start.col + 1)
    lines = diagnostic.message.splitlines()
    formatted = " {}\t{:<12}\t{:<10}\t{}".format(
        location, diagnostic.source, format_severity(diagnostic.severity), lines[0])
    for line in lines[1:]:
        formatted = formatted + "\n {:<12}\t{:<12}\t{:<10}\t{}".format("", "", "", line)
    return formatted


phantom_sets_by_buffer = {}  # type: Dict[int, sublime.PhantomSet]


def update_diagnostics_phantoms(view: sublime.View, diagnostics: 'List[Diagnostic]') -> None:
    global phantom_sets_by_buffer

    buffer_id = view.buffer_id()
    if not settings.show_diagnostics_phantoms or view.is_dirty():
        phantoms = None
    else:
        phantoms = list(
            create_phantom(view, diagnostic) for diagnostic in diagnostics)
    if phantoms:
        phantom_set = phantom_sets_by_buffer.get(buffer_id)
        if not phantom_set:
            phantom_set = sublime.PhantomSet(view, "lsp_diagnostics")
            phantom_sets_by_buffer[buffer_id] = phantom_set
        phantom_set.update(phantoms)
    else:
        phantom_sets_by_buffer.pop(buffer_id, None)


def get_point_diagnostics(view, point):
    diagnostics = get_view_diagnostics(view)
    return tuple(
        diagnostic for diagnostic in diagnostics
        if range_to_region(diagnostic.range, view).contains(point)
    )


def update_diagnostics_regions(view: sublime.View, diagnostics: 'List[Diagnostic]', severity: int):
    region_name = "lsp_" + format_severity(severity)
    if settings.show_diagnostics_phantoms and not view.is_dirty():
        regions = None
    else:
        regions = list(range_to_region(diagnostic.range, view) for diagnostic in diagnostics
                       if diagnostic.severity == severity)
    if regions:
        scope_name = diagnostic_severity_scopes[severity]
        view.add_regions(
            region_name, regions, scope_name, settings.diagnostics_gutter_marker,
            UNDERLINE_FLAGS if settings.diagnostics_highlight_style == "underline" else BOX_FLAGS)
    else:
        view.erase_regions(region_name)


def update_diagnostics_in_view(view: sublime.View):
    if view and view.is_valid():
        file_diagnostics = get_view_diagnostics(view)
        for severity in range(
                DiagnosticSeverity.Error,
                DiagnosticSeverity.Error + settings.show_diagnostics_severity_level):
            update_diagnostics_regions(view, file_diagnostics, severity)

        update_diagnostics_phantoms(view, file_diagnostics)


def get_view_diagnostics(view) -> 'List[Diagnostic]':
    if view.window():
        if view.file_name():
            return windows.lookup(view.window())._diagnostics.get_by_path(view.file_name())
    return []


def get_line_diagnostics(view, point):
    row, _ = view.rowcol(point)
    diagnostics = get_view_diagnostics(view)
    return tuple(
        diagnostic for diagnostic in diagnostics
        if diagnostic.range.start.row <= row <= diagnostic.range.end.row
    )


def get_window_diagnostics(window):
    return windows.lookup(window)._diagnostics.get()


def update_diagnostics_in_status_bar(view: sublime.View):
    errors = 0
    warnings = 0

    window = view.window()
    if window:
        diagnostics_by_file = get_window_diagnostics(window)

        if diagnostics_by_file:
            for file_path, source_diagnostics in diagnostics_by_file.items():

                if source_diagnostics:
                    for origin, diagnostics in source_diagnostics.items():
                        for diagnostic in diagnostics:

                            if diagnostic.severity == DiagnosticSeverity.Error:
                                errors += 1
                            if diagnostic.severity == DiagnosticSeverity.Warning:
                                warnings += 1

        if errors > 0 or warnings > 0:
            count = 'E: {} W: {}'.format(errors, warnings)
        else:
            count = ""
        view.set_status('lsp_errors_warning_count', count)


def update_count_in_status_bar(view):
    if settings.show_diagnostics_count_in_view_status:
        update_diagnostics_in_status_bar(view)


global_events.subscribe("document.diagnostics",
                        lambda update: handle_diagnostics(update))
global_events.subscribe("view.on_activated_async", update_count_in_status_bar)


def handle_diagnostics(update: DiagnosticsUpdate):
    window = update.window
    view = window.find_open_file(update.file_path)
    if view:
        update_diagnostics_in_view(view)
        if settings.show_diagnostics_count_in_view_status:
            update_diagnostics_in_status_bar(view)
    else:
        debug('view not found')
    update_diagnostics_panel(window)


class DiagnosticsCursorListener(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        self.view = view
        self.has_status = False

    @classmethod
    def is_applicable(cls, view_settings):
        syntax = view_settings.get('syntax')
        return settings.show_diagnostics_in_view_status and syntax and is_supported_syntax(syntax, client_configs.all)

    def on_selection_modified_async(self):
        selections = self.view.sel()
        if len(selections) > 0:
            pos = selections[0].begin()
            line_diagnostics = get_line_diagnostics(self.view, pos)
            if len(line_diagnostics) > 0:
                self.show_diagnostics_status(line_diagnostics)
            elif self.has_status:
                self.clear_diagnostics_status()

    def show_diagnostics_status(self, line_diagnostics):
        self.has_status = True
        self.view.set_status('lsp_diagnostics', line_diagnostics[0].message)

    def clear_diagnostics_status(self):
        self.view.erase_status('lsp_diagnostics')
        self.has_status = False


class LspShowDiagnosticsPanelCommand(sublime_plugin.WindowCommand):
    def run(self):
        ensure_diagnostics_panel(self.window)
        active_panel = self.window.active_panel()
        is_active_panel = (active_panel == "output.diagnostics")

        if is_active_panel:
            self.window.run_command("hide_panel", {"panel": "output.diagnostics"})
        else:
            self.window.run_command("show_panel", {"panel": "output.diagnostics"})


class LspClearDiagnosticsCommand(sublime_plugin.WindowCommand):
    def run(self):
        windows.lookup(self.window)._diagnostics.clear()


def ensure_diagnostics_panel(window: sublime.Window) -> 'Optional[sublime.View]':
    return ensure_panel(window, "diagnostics", r"^\s*\S\s+(\S.*):$", r"^\s+([0-9]+):?([0-9]+).*$",
                        "Packages/" + PLUGIN_NAME + "/Syntaxes/Diagnostics.sublime-syntax")


def update_diagnostics_panel(window: sublime.Window):
    assert window, "missing window!"

    if not window.is_valid():
        debug('ignoring update to closed window')
        return

    base_dir = windows.lookup(window).get_project_path()

    diagnostics_by_file = get_window_diagnostics(window)
    if diagnostics_by_file is not None:

        active_panel = window.active_panel()
        is_active_panel = (active_panel == "output.diagnostics")

        if diagnostics_by_file:
            panel = ensure_diagnostics_panel(window)
            assert panel, "must have a panel now!"
            panel.settings().set("result_base_dir", base_dir)

            auto_open_panel = False
            to_render = []
            for file_path, source_diagnostics in diagnostics_by_file.items():
                try:
                    relative_file_path = os.path.relpath(file_path, base_dir) if base_dir else file_path
                except ValueError:
                    relative_file_path = file_path
                if source_diagnostics:
                    formatted = format_diagnostics(relative_file_path, source_diagnostics)
                    if formatted:
                        to_render.append(formatted)
                        if not auto_open_panel:
                            auto_open_panel = has_relevant_diagnostics(source_diagnostics)

            panel.set_read_only(False)
            panel.run_command("lsp_update_panel", {"characters": "\n".join(to_render)})
            panel.set_read_only(True)

            if settings.auto_show_diagnostics_panel and not active_panel:
                if auto_open_panel:
                    window.run_command("show_panel",
                                       {"panel": "output.diagnostics"})

        else:
            panel = window.find_output_panel("diagnostics")
            if panel:
                panel.run_command("lsp_clear_panel")
                if is_active_panel:
                    window.run_command("hide_panel",
                                       {"panel": "output.diagnostics"})


def has_relevant_diagnostics(origin_diagnostics):
    for origin, diagnostics in origin_diagnostics.items():
        for diagnostic in diagnostics:
            # debug('severity check', diagnostic.severity, '<=', settings.auto_show_diagnostics_panel_level)
            if diagnostic.severity <= settings.auto_show_diagnostics_panel_level:
                return True

    return False


def format_diagnostics(file_path, origin_diagnostics):
    content = ""
    for origin, diagnostics in origin_diagnostics.items():
        for diagnostic in diagnostics:
            if diagnostic.severity <= settings.show_diagnostics_severity_level:
                item = format_diagnostic(diagnostic)
                content += item + "\n"
    if content:
        return " ◌ {}:\n{}".format(file_path, content)
    else:
        return None
