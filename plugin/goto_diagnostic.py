from __future__ import annotations
from .core.constants import DIAGNOSTIC_KINDS
from .core.diagnostics_storage import is_severity_included
from .core.diagnostics_storage import ParsedUri
from .core.input_handlers import PreselectedListInputHandler
from .core.paths import project_base_dir
from .core.paths import project_path
from .core.paths import simple_project_path
from .core.protocol import Diagnostic
from .core.protocol import DiagnosticSeverity
from .core.protocol import DocumentUri
from .core.protocol import Location
from .core.registry import windows
from .core.sessions import Session
from .core.settings import userprefs
from .core.types import ClientConfig
from .core.url import parse_uri, unparse_uri
from .core.views import diagnostic_severity
from .core.views import format_diagnostic_for_html
from .core.views import format_diagnostic_source_and_code
from .core.views import format_severity
from .core.views import get_uri_and_position_from_location
from .core.views import MissingUriError
from .core.views import to_encoded_filename
from .core.views import uri_from_view
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Iterator
from typing import cast
import functools
import os
import sublime
import sublime_plugin


PREVIEW_PANE_CSS = """
    .diagnostics {padding: 0.5em}
    .diagnostics a {color: var(--bluish)}
    .diagnostics.error {background-color: color(var(--redish) alpha(0.25)); white-space: pre-wrap}
    .diagnostics.warning {background-color: color(var(--yellowish) alpha(0.25))}
    .diagnostics.info {background-color: color(var(--bluish) alpha(0.25))}
    .diagnostics.hint {background-color: color(var(--bluish) alpha(0.25))}
    """


def get_sessions(window: sublime.Window) -> Iterator[Session]:
    wm = windows.lookup(window)
    if wm is not None:
        yield from wm._sessions


class LspGotoDiagnosticCommand(sublime_plugin.WindowCommand):
    def run(self, uri: DocumentUri | None, diagnostic: dict | None) -> None:  # type: ignore
        pass

    def is_enabled(self, uri: DocumentUri | None = None, diagnostic: dict | None = None) -> bool:  # type: ignore
        view = self.window.active_view()
        if view is None:
            return False
        if uri == "$view_uri":
            try:
                uri = uri_from_view(view)
            except MissingUriError:
                return False
        max_severity = userprefs().diagnostics_panel_include_severity_level
        if uri:
            parsed_uri = parse_uri(uri)
            return any(diagnostic for session in get_sessions(self.window)
                       for diagnostic in session.diagnostics.diagnostics_by_parsed_uri(parsed_uri)
                       if is_severity_included(max_severity)(diagnostic))
        return any(diagnostic for session in get_sessions(self.window)
                   for diagnostics in session.diagnostics.values()
                   for diagnostic in diagnostics
                   if is_severity_included(max_severity)(diagnostic))

    def input(self, args: dict) -> sublime_plugin.CommandInputHandler | None:
        uri, diagnostic = args.get("uri"), args.get("diagnostic")
        view = self.window.active_view()
        if view is None:
            return None
        if not uri:
            return DiagnosticUriInputHandler(self.window, view)
        if uri == "$view_uri":
            try:
                uri = uri_from_view(view)
            except MissingUriError:
                return None
            return DiagnosticUriInputHandler(self.window, view, uri)
        if not diagnostic:
            return DiagnosticInputHandler(self.window, view, uri)
        return None

    def input_description(self) -> str:
        return "Goto Diagnostic"


class DiagnosticUriInputHandler(PreselectedListInputHandler):
    _preview: sublime.View | None = None
    uri: DocumentUri | None = None

    def __init__(self, window: sublime.Window, view: sublime.View, initial_value: DocumentUri | None = None) -> None:
        super().__init__(window, initial_value)
        self.window = window
        self.view = view

    def name(self) -> str:
        return "uri"

    def get_list_items(self) -> tuple[list[sublime.ListInputItem], int]:
        max_severity = userprefs().diagnostics_panel_include_severity_level
        # collect severities and location of first diagnostic per uri
        severities_per_path: OrderedDict[ParsedUri, list[DiagnosticSeverity]] = OrderedDict()
        self.first_locations: dict[ParsedUri, tuple[Session, Location]] = dict()
        for session in get_sessions(self.window):
            for parsed_uri, severity in session.diagnostics.filter_map_diagnostics_flat_async(
                    is_severity_included(max_severity), lambda _, diagnostic: diagnostic_severity(diagnostic)):
                severities_per_path.setdefault(parsed_uri, []).append(severity)
                if parsed_uri not in self.first_locations:
                    severities_per_path.move_to_end(parsed_uri)
                    diagnostics = session.diagnostics.diagnostics_by_parsed_uri(parsed_uri)
                    if diagnostics:
                        self.first_locations[parsed_uri] = session, diagnostic_location(parsed_uri, diagnostics[0])
        # build items
        list_items = list()
        selected = 0
        for i, (parsed_uri, severities) in enumerate(severities_per_path.items()):
            counts = Counter(severities)
            text = f"{format_severity(min(counts))}: {self._simple_project_path(parsed_uri)}"
            annotation = f"E: {counts.get(DiagnosticSeverity.Error, 0)}, W: {counts.get(DiagnosticSeverity.Warning, 0)}"
            kind = DIAGNOSTIC_KINDS[min(counts)]
            uri = unparse_uri(parsed_uri)
            if uri == self.uri:
                selected = i  # restore selection after coming back from diagnostics list
            list_items.append(sublime.ListInputItem(text, uri, annotation=annotation, kind=kind))
        return list_items, selected

    def placeholder(self) -> str:
        return "Select file"

    def next_input(self, args: dict) -> sublime_plugin.CommandInputHandler | None:
        uri, diagnostic = args.get("uri"), args.get("diagnostic")
        if uri is None:
            return None
        if diagnostic is None:
            self._preview = None
            return DiagnosticInputHandler(self.window, self.view, uri)
        return sublime_plugin.BackInputHandler()

    def confirm(self, value: DocumentUri | None) -> None:
        self.uri = value

    def description(self, value: DocumentUri, text: str) -> str:
        return self._project_path(parse_uri(value))

    def cancel(self) -> None:
        if self._preview is not None:
            sheet = self._preview.sheet()
            if sheet and sheet.is_transient():
                self._preview.close()
        self.window.focus_view(self.view)

    def preview(self, value: DocumentUri | None) -> str:
        if not value or not hasattr(self, 'first_locations'):
            return ""
        parsed_uri = parse_uri(value)
        session, location = self.first_locations[parsed_uri]
        scheme, _ = parsed_uri
        if scheme == "file":
            self._preview = open_location(session, location, flags=sublime.NewFileFlags.TRANSIENT)
        return ""

    def _simple_project_path(self, parsed_uri: ParsedUri) -> str:
        scheme, path = parsed_uri
        if scheme == "file":
            path = str(simple_project_path(map(Path, self.window.folders()), Path(path))) or path
        return path

    def _project_path(self, parsed_uri: ParsedUri) -> str:
        scheme, path = parsed_uri
        if scheme == "file":
            relative_path = project_path(map(Path, self.window.folders()), Path(path))
            return str(relative_path) if relative_path else os.path.basename(path)
        return path


class DiagnosticInputHandler(sublime_plugin.ListInputHandler):
    _preview: sublime.View | None = None

    def __init__(self, window: sublime.Window, view: sublime.View, uri: DocumentUri) -> None:
        self.window = window
        self.view = view
        self.sessions = list(get_sessions(window))
        self.parsed_uri = parse_uri(uri)

    def name(self) -> str:
        return "diagnostic"

    def list_items(self) -> list[sublime.ListInputItem]:
        list_items: list[sublime.ListInputItem] = []
        max_severity = userprefs().diagnostics_panel_include_severity_level
        for i, session in enumerate(self.sessions):
            for diagnostic in filter(is_severity_included(max_severity),
                                     session.diagnostics.diagnostics_by_parsed_uri(self.parsed_uri)):
                lines = diagnostic["message"].splitlines()
                first_line = lines[0] if lines else ""
                if len(lines) > 1:
                    first_line += " …"
                text = f"{format_severity(diagnostic_severity(diagnostic))}: {first_line}"
                annotation = format_diagnostic_source_and_code(diagnostic)
                kind = DIAGNOSTIC_KINDS[diagnostic_severity(diagnostic)]
                list_items.append(sublime.ListInputItem(text, [i, diagnostic], annotation=annotation, kind=kind))
        return list_items

    def placeholder(self) -> str:
        return "Select diagnostic"

    def next_input(self, args: dict) -> sublime_plugin.CommandInputHandler | None:
        return None if args.get("diagnostic") else sublime_plugin.BackInputHandler()  # type: ignore

    def confirm(self, value: list | None) -> None:
        if not value:
            return
        i = cast(int, value[0])
        diagnostic = cast(Diagnostic, value[1])
        session = self.sessions[i]
        location = self._get_location(diagnostic)
        scheme, _ = self.parsed_uri
        if scheme == "file":
            open_location(session, self._get_location(diagnostic))
        else:
            sublime.set_timeout_async(functools.partial(session.open_location_async, location))

    def cancel(self) -> None:
        if self._preview is not None:
            sheet = self._preview.sheet()
            if sheet and sheet.is_transient():
                self._preview.close()
        self.window.focus_view(self.view)

    def preview(self, value: list | None) -> str | sublime.Html:
        if not value:
            return ""
        i = cast(int, value[0])
        diagnostic = cast(Diagnostic, value[1])
        session = self.sessions[i]
        base_dir = None
        scheme, path = self.parsed_uri
        if scheme == "file":
            self._preview = open_location(session, self._get_location(diagnostic), flags=sublime.NewFileFlags.TRANSIENT)
            base_dir = project_base_dir(map(Path, self.window.folders()), Path(path))
        return diagnostic_html(session.config, truncate_message(diagnostic), base_dir)

    def _get_location(self, diagnostic: Diagnostic) -> Location:
        return diagnostic_location(self.parsed_uri, diagnostic)


def diagnostic_location(parsed_uri: ParsedUri, diagnostic: Diagnostic) -> Location:
    return {
        'uri': unparse_uri(parsed_uri),
        'range': diagnostic["range"]
    }


def open_location(
    session: Session, location: Location, flags: sublime.NewFileFlags = sublime.NewFileFlags.NONE, group: int = -1
) -> sublime.View:
    uri, position = get_uri_and_position_from_location(location)
    file_name = to_encoded_filename(session.config.map_server_uri_to_client_path(uri), position)
    return session.window.open_file(file_name, flags=flags | sublime.NewFileFlags.ENCODED_POSITION, group=group)


def diagnostic_html(config: ClientConfig, diagnostic: Diagnostic, base_dir: Path | None) -> sublime.Html:
    content = format_diagnostic_for_html(
        config, truncate_message(diagnostic), None if base_dir is None else str(base_dir))
    return sublime.Html('<style>{}</style><div class="diagnostics {}">{}</div>'.format(
        PREVIEW_PANE_CSS, format_severity(diagnostic_severity(diagnostic)), content))


def truncate_message(diagnostic: Diagnostic, max_lines: int = 6) -> Diagnostic:
    lines = diagnostic["message"].splitlines()
    if len(lines) <= max_lines:
        return diagnostic
    diagnostic = diagnostic.copy()
    diagnostic["message"] = "\n".join(lines[:max_lines - 1]) + " …\n"
    return diagnostic
