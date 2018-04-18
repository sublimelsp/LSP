import html
import os
import sublime
import sublime_plugin

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass

from .core.settings import settings, PLUGIN_NAME
from .core.protocol import Diagnostic, DiagnosticSeverity
from .core.events import Events
from .core.configurations import is_supported_syntax
from .core.diagnostics import DiagnosticsUpdate, get_window_diagnostics, get_line_diagnostics
from .core.workspace import get_project_path
from .core.panels import create_output_panel

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

UNDERLINE_FLAGS = (sublime.DRAW_SQUIGGLY_UNDERLINE
                   | sublime.DRAW_NO_OUTLINE
                   | sublime.DRAW_NO_FILL
                   | sublime.DRAW_EMPTY_AS_OVERWRITE)

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
    region = diagnostic.range.to_region(view)
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


def update_diagnostics_phantoms(view: sublime.View, diagnostics: 'List[Diagnostic]'):
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


def update_diagnostics_regions(view: sublime.View, diagnostics: 'List[Diagnostic]', severity: int):
    region_name = "lsp_" + format_severity(severity)
    if settings.show_diagnostics_phantoms and not view.is_dirty():
        regions = None
    else:
        regions = list(diagnostic.range.to_region(view) for diagnostic in diagnostics
                       if diagnostic.severity == severity)
    if regions:
        scope_name = diagnostic_severity_scopes[severity]
        view.add_regions(
            region_name, regions, scope_name, settings.diagnostics_gutter_marker,
            UNDERLINE_FLAGS if settings.diagnostics_highlight_style == "underline" else BOX_FLAGS)
    else:
        view.erase_regions(region_name)


def update_diagnostics_in_view(view: sublime.View, diagnostics: 'List[Diagnostic]'):
    if view and view.is_valid():
        update_diagnostics_phantoms(view, diagnostics)
        for severity in range(DiagnosticSeverity.Error, DiagnosticSeverity.Information):
            update_diagnostics_regions(view, diagnostics, severity)


def update_diagnostics_in_status_bar(window: sublime.Window):
    errors = 0
    warnings = 0

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

    message = 'E: {} W: {}'.format(errors, warnings)
    view = window.active_view()
    if view:
        view.set_status('lsp_errors_warning_count', message)


def update_count_in_status_bar(view):
    update_diagnostics_in_status_bar(view.window())


Events.subscribe("document.diagnostics",
                 lambda update: handle_diagnostics(update))
Events.subscribe("view.on_activated_async", update_count_in_status_bar)


def handle_diagnostics(update: DiagnosticsUpdate):
    window = update.window
    view = window.find_open_file(update.file_path)
    if view:
        update_diagnostics_in_view(view, update.diagnostics)
    update_diagnostics_panel(window)
    update_diagnostics_in_status_bar(window)


class DiagnosticsCursorListener(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        self.view = view
        self.has_status = False

    @classmethod
    def is_applicable(cls, view_settings):
        syntax = view_settings.get('syntax')
        return settings.show_diagnostics_in_view_status and syntax and is_supported_syntax(syntax)

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


def create_diagnostics_panel(window):
    panel = create_output_panel(window, "diagnostics")
    panel.settings().set("result_file_regex", r"^\s*\S\s+(\S.*):$")
    panel.settings().set("result_line_regex", r"^\s+([0-9]+):?([0-9]+).*$")
    panel.assign_syntax("Packages/" + PLUGIN_NAME +
                        "/Syntaxes/Diagnostics.sublime-syntax")
    # Call create_output_panel a second time after assigning the above
    # settings, so that it'll be picked up as a result buffer
    # see: Packages/Default/exec.py#L228-L230
    panel = window.create_output_panel("diagnostics")
    return panel


def ensure_diagnostics_panel(window: sublime.Window):
    return window.find_output_panel("diagnostics") or create_diagnostics_panel(window)


def update_diagnostics_panel(window: sublime.Window):
    assert window, "missing window!"
    base_dir = get_project_path(window)

    panel = ensure_diagnostics_panel(window)
    assert panel, "must have a panel now!"

    diagnostics_by_file = get_window_diagnostics(window)
    if diagnostics_by_file is not None:
        active_panel = window.active_panel()
        is_active_panel = (active_panel == "output.diagnostics")
        panel.settings().set("result_base_dir", base_dir)
        panel.set_read_only(False)
        if diagnostics_by_file:
            to_render = []
            for file_path, source_diagnostics in diagnostics_by_file.items():
                relative_file_path = os.path.relpath(file_path, base_dir) if base_dir else file_path
                if source_diagnostics:
                    to_render.append(format_diagnostics(relative_file_path, source_diagnostics))
            panel.run_command("lsp_update_panel", {"characters": "\n".join(to_render)})
            if settings.auto_show_diagnostics_panel and not active_panel:
                window.run_command("show_panel",
                                   {"panel": "output.diagnostics"})
        else:
            panel.run_command("lsp_clear_panel")
            if is_active_panel:
                window.run_command("hide_panel",
                                   {"panel": "output.diagnostics"})
        panel.set_read_only(True)


def format_diagnostics(file_path, origin_diagnostics):
    content = " ◌ {}:\n".format(file_path)
    for origin, diagnostics in origin_diagnostics.items():
        for diagnostic in diagnostics:
            item = format_diagnostic(diagnostic)
            content += item + "\n"
    return content
