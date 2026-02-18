from __future__ import annotations

from ..protocol import Diagnostic
from ..protocol import DiagnosticSeverity
from ..protocol import DocumentUri
from ..protocol import Location
from ..protocol import LocationLink
from .core.constants import DIAGNOSTIC_KINDS
from .core.input_handlers import PreselectedListInputHandler
from .core.paths import simple_project_path
from .core.protocol import Point
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.registry import LspWindowCommand
from .core.sessions import Session
from .core.settings import userprefs
from .core.types import method_to_capability
from .core.url import parse_uri
from .core.views import diagnostic_severity
from .core.views import first_selection_region
from .core.views import get_symbol_kind_from_scope
from .core.views import position_to_offset
from .core.views import range_to_region
from .core.views import text_document_position_params
from .core.views import to_encoded_filename
from .core.views import uri_from_view
from .locationpicker import LocationPicker
from .locationpicker import open_location_async
from collections import Counter
from functools import partial
from os.path import basename
from pathlib import Path
from typing import cast
from typing import TypedDict
import sublime
import sublime_plugin


class LspGotoCommand(LspTextCommand):

    method = ''
    placeholder_text = ''
    fallback_command = ''

    def is_enabled(
        self,
        event: dict | None = None,
        point: int | None = None,
        side_by_side: bool = False,
        force_group: bool = True,
        fallback: bool = False,
        group: int = -1
    ) -> bool:
        return fallback or super().is_enabled(event, point)

    def is_visible(
        self,
        event: dict | None = None,
        point: int | None = None,
        side_by_side: bool = False,
        force_group: bool = True,
        fallback: bool = False,
        group: int = -1
    ) -> bool:
        if self.applies_to_context_menu(event):
            return self.is_enabled(event, point, side_by_side, force_group, fallback, group)
        return True

    def run(
        self,
        _: sublime.Edit,
        event: dict | None = None,
        point: int | None = None,
        side_by_side: bool = False,
        force_group: bool = True,
        fallback: bool = False,
        group: int = -1
    ) -> None:
        position = get_position(self.view, event, point)
        session = self.best_session(self.capability, position)
        if session and position is not None:
            params = text_document_position_params(self.view, position)
            request = Request(self.method, params, self.view, progress=True)
            session.send_request(
                request,
                partial(self._handle_response_async, session, side_by_side, force_group, fallback, group, position)
            )
        else:
            self._handle_no_results(fallback, side_by_side)

    def _handle_response_async(
        self,
        session: Session,
        side_by_side: bool,
        force_group: bool,
        fallback: bool,
        group: int,
        position: int,
        response: None | Location | list[Location] | list[LocationLink]
    ) -> None:
        if isinstance(response, dict):
            self.view.run_command("add_jump_record", {"selection": [(r.a, r.b) for r in self.view.sel()]})
            open_location_async(session, response, side_by_side, force_group, group)
        elif isinstance(response, list):
            if len(response) == 0:
                self._handle_no_results(fallback, side_by_side)
            elif len(response) == 1:
                self.view.run_command("add_jump_record", {"selection": [(r.a, r.b) for r in self.view.sel()]})
                open_location_async(session, response[0], side_by_side, force_group, group)
            else:
                self.view.run_command("add_jump_record", {"selection": [(r.a, r.b) for r in self.view.sel()]})
                placeholder = self.placeholder_text + " " + self.view.substr(self.view.word(position))
                kind = get_symbol_kind_from_scope(self.view.scope_name(position))
                sublime.set_timeout(
                    partial(LocationPicker,
                            self.view, session, response, side_by_side, force_group, group, placeholder, kind)
                )
        else:
            self._handle_no_results(fallback, side_by_side)

    def _handle_no_results(self, fallback: bool = False, side_by_side: bool = False) -> None:
        if window := self.view.window():
            if fallback and self.fallback_command:
                window.run_command(self.fallback_command, {"side_by_side": side_by_side})
            else:
                window.status_message("No results found")


class LspSymbolDefinitionCommand(LspGotoCommand):
    method = "textDocument/definition"
    capability = method_to_capability(method)[0]
    placeholder_text = "Definitions of"
    fallback_command = "goto_definition"


class LspSymbolTypeDefinitionCommand(LspGotoCommand):
    method = "textDocument/typeDefinition"
    capability = method_to_capability(method)[0]
    placeholder_text = "Type Definitions of"


class LspSymbolDeclarationCommand(LspGotoCommand):
    method = "textDocument/declaration"
    capability = method_to_capability(method)[0]
    placeholder_text = "Declarations of"


class LspSymbolImplementationCommand(LspGotoCommand):
    method = "textDocument/implementation"
    capability = method_to_capability(method)[0]
    placeholder_text = "Implementations of"


class DiagnosticData(TypedDict):
    session_name: str
    diagnostic: Diagnostic


class LspGotoDiagnosticCommand(LspWindowCommand):

    def run(self, uri: DocumentUri | None, diagnostic: DiagnosticData | None) -> None:
        pass

    def is_enabled(self) -> bool:
        max_severity = userprefs().diagnostics_panel_include_severity_level
        return any(any(session.diagnostics.get_diagnostics(max_severity).values()) for session in self.sessions())

    def input_description(self) -> str:
        return 'Goto Diagnostic'

    def input(self, args: dict) -> sublime_plugin.CommandInputHandler | None:
        view = self.window.active_view()
        if not view:
            return None
        sessions = list(self.sessions())
        if (uri := args.get('uri')) and uri != "$view_uri":  # for backwards compatibility with previous command args
            return DiagnosticUriInputHandler(self.window, view, sessions, uri)
        elif (uri := view.settings().get('lsp_uri')) and self._has_diagnostics(uri):
            return DiagnosticUriInputHandler(self.window, view, sessions, uri)
        return DiagnosticUriInputHandler(self.window, view, sessions)

    def _has_diagnostics(self, uri: DocumentUri) -> bool:
        max_severity = userprefs().diagnostics_panel_include_severity_level
        return any(session.diagnostics.get_diagnostics_for_uri(uri, max_severity) for session in self.sessions())


class DiagnosticUriInputHandler(PreselectedListInputHandler):

    def __init__(
        self,
        window: sublime.Window,
        initial_view: sublime.View,
        sessions: list[Session],
        initial_value: DocumentUri | None = None
    ) -> None:
        super().__init__(window, initial_value)
        self.window = window
        self.initial_view = initial_view
        self.sessions = sessions
        self.uri: DocumentUri | None = None
        self._preview: sublime.View | None = None
        self._max_severity = userprefs().diagnostics_panel_include_severity_level

    def name(self) -> str:
        return 'uri'

    def placeholder(self) -> str:
        return 'Select file'

    def get_list_items(self) -> tuple[list[sublime.ListInputItem], int]:
        severity_counts_per_uri: dict[DocumentUri, Counter[DiagnosticSeverity]] = {}
        for session in self.sessions:
            for uri, diagnostics in session.diagnostics.get_diagnostics(self._max_severity).items():
                if diagnostics:
                    severity_counts_per_uri.setdefault(uri, Counter()).update(map(diagnostic_severity, diagnostics))
        window_folders = [Path(folder) for folder in self.window.folders()]
        items: list[sublime.ListInputItem] = []
        selected_index = 0
        for index, (uri, counts) in enumerate(sorted(severity_counts_per_uri.items())):
            if uri == self.uri:
                selected_index = index
            scheme, path = parse_uri(uri)
            if scheme == 'file':
                path = str(simple_project_path(window_folders, Path(path)) or path)
            annotation = f'E: {counts[DiagnosticSeverity.Error]}, W: {counts[DiagnosticSeverity.Warning]}'
            kind = DIAGNOSTIC_KINDS[min(counts)]
            items.append(sublime.ListInputItem(path, uri, annotation=annotation, kind=kind))
        return items, selected_index

    def preview(self, value: DocumentUri | None) -> str:
        if value:
            for session in self.sessions:
                if session_buffer := session.get_session_buffer_for_uri_async(value):
                    self._preview = session_buffer.get_view_in_group()
                    self.window.focus_view(self._preview)
                    break
            else:
                scheme, path = parse_uri(value)
                if scheme == 'file':
                    self._preview = self.window.open_file(path, sublime.NewFileFlags.TRANSIENT)
        return ''

    def cancel(self) -> None:
        _focus_initial_view(self.window, self.initial_view, self._preview)

    def confirm(self, value: DocumentUri | None) -> None:
        self.uri = value

    def next_input(self, args: dict) -> sublime_plugin.CommandInputHandler | None:
        if uri := args.get('uri'):
            diagnostics: list[DiagnosticData] = []
            for session in self.sessions:
                diagnostics.extend({
                    'session_name': session.config.name,
                    'diagnostic': diagnostic
                } for diagnostic in session.diagnostics.get_diagnostics_for_uri(uri, self._max_severity))
            diagnostics.sort(
                key=lambda d: (Point.from_lsp(d['diagnostic']['range']['start']), diagnostic_severity(d['diagnostic']))
            )
            view: sublime.View | None = None
            if self._preview:
                if uri_from_view(self._preview) == uri:
                    view = self._preview
                elif (preview_sheet := self._preview.sheet()) and preview_sheet.is_transient():
                    self._preview.close()
            return DiagnosticInputHandler(
                self.window, self.initial_view, view, self.sessions, uri, diagnostics)
        return None

    def description(self, value: DocumentUri, text: str) -> str:
        scheme, path = parse_uri(value)
        return basename(path) if scheme == 'file' else value.split('/')[-1]


class DiagnosticInputHandler(sublime_plugin.ListInputHandler):

    def __init__(
        self,
        window: sublime.Window,
        initial_view: sublime.View,
        _preview: sublime.View | None,
        sessions: list[Session],
        uri: DocumentUri,
        diagnostics: list[DiagnosticData]
    ) -> None:
        super().__init__()
        self.window = window
        self.initial_view = initial_view
        self._preview = _preview
        self.sessions = sessions
        self.uri = uri
        self.diagnostics = diagnostics

    def name(self) -> str:
        return 'diagnostic'

    def list_items(self) -> tuple[list[sublime.ListInputItem], int]:
        items: list[sublime.ListInputItem] = []
        selected_index = 0
        caret_pos = region.b if self._preview and (region := first_selection_region(self._preview)) is not None else 0
        for index, diagnostic_data in enumerate(self.diagnostics):
            diagnostic = diagnostic_data['diagnostic']
            message = diagnostic['message'] or '…'
            severity = diagnostic_severity(diagnostic)
            text = f"{'_EWIH'[severity]}: {message.splitlines()[0]}"
            value = cast(dict, diagnostic_data)
            code = str(diagnostic.get('code', ''))
            kind = DIAGNOSTIC_KINDS[severity]
            items.append(sublime.ListInputItem(text, value, annotation=code, kind=kind))
            if self._preview and position_to_offset(diagnostic['range']['start'], self._preview) <= caret_pos:
                selected_index = index
        return items, selected_index

    def preview(self, value: DiagnosticData | None) -> str | sublime.Html:
        if value:
            diagnostic = value['diagnostic']
            if self.uri.startswith('file:'):
                self._open_file(value, transient=True)
            elif self._preview:
                self._preview.show_at_center(range_to_region(diagnostic['range'], self._preview))
            source = diagnostic.get('source', '')
            if code := str(diagnostic.get('code', '')):
                if code_description := diagnostic.get('codeDescription'):
                    href = code_description['href']
                    return sublime.Html(
                        f"{source}(<a href='{href}' title='{href}' style='color: var(--bluish)'>{code}</a>)")
                return f"{source}({code})"
            return source
        return ''

    def cancel(self) -> None:
        _focus_initial_view(self.window, self.initial_view, self._preview)

    def confirm(self, value: DiagnosticData | None) -> None:
        if not value:
            return
        scheme, _ = parse_uri(self.uri)
        if scheme == 'file':
            self._open_file(value)
        elif session := self._session(value):
            location: Location = {'uri': self.uri, 'range': value['diagnostic']['range']}
            sublime.set_timeout_async(partial(session.open_location_async, location))

    def _session(self, value: DiagnosticData) -> Session | None:
        session_name = value['session_name']
        for session in self.sessions:
            if session.config.name == session_name:
                return session
        return None

    def _open_file(self, value: DiagnosticData, *, transient: bool = False) -> sublime.View | None:
        if session := self._session(value):
            filename = to_encoded_filename(
                session.config.map_server_uri_to_client_path(self.uri),
                value['diagnostic']['range']['start']
            )
            flags = sublime.NewFileFlags.ENCODED_POSITION
            if transient:
                flags |= sublime.NewFileFlags.TRANSIENT
            return self.window.open_file(filename, flags)
        return None


def _focus_initial_view(window: sublime.Window, initial_view: sublime.View, preview: sublime.View | None) -> None:
    if preview and (preview_sheet := preview.sheet()) and preview_sheet.is_transient():
        preview.close()
    window.focus_view(initial_view)
