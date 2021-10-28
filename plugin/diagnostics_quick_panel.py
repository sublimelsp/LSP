from .core.diagnostics_manager import ParsedUri, is_severity_included
from .core.protocol import Diagnostic, DiagnosticSeverity, DocumentUri, Location, LocationLink, Position
from .core.registry import windows
from .core.sessions import Session
from .core.typing import Iterable, Iterator, List, Optional, Tuple, Union
from .core.url import parse_uri, unparse_uri
from .core.views import MissingUriError, diagnostic_severity, diagnostic_source, uri_from_view
from .locationpicker import LocationPicker, OnModifierKeysAcitonMap
from pathlib import Path
import functools
import html
import sublime
import sublime_plugin
import weakref

# TODO: should be user settings
GOTO_DIAGNOSTIC_SEVERITY_MAX_LEVEL = DiagnosticSeverity.Hint
GOTO_DIAGNOSTIC_MAX_DETAILS_LINES = 2
DIAGNOSTIC_KIND_TUPLE = {
    DiagnosticSeverity.Error: (sublime.KIND_ID_COLOR_BLUISH, "e", ""),
    DiagnosticSeverity.Warning: (sublime.KIND_ID_COLOR_YELLOWISH, "w", ""),
    DiagnosticSeverity.Information: (sublime.KIND_ID_COLOR_GREENISH, "i", ""),
    DiagnosticSeverity.Hint: (sublime.KIND_ID_COLOR_GREENISH, "h", ""),
}

GotoDiagnosticItem = Tuple[Tuple[weakref.ReferenceType, Union[Location, LocationLink]], sublime.QuickPanelItem]


class LspGotoDiagnosticCommandBase(sublime_plugin.WindowCommand):
    def _run(self) -> None:
        view = self.window.active_view()
        if view is None:
            return
        wm = windows.lookup(self.window)
        if wm is not None:
            locations, items = tuple(zip(*tuple(self._diagnostic_items())))  # transpose
            LocationPicker(view, locations, items, side_by_side=False, on_modifier_keys=self._get_on_modifier_keys())

    def is_enabled(self) -> bool:
        for session in self._get_sessions():
            if session.diagnostics_manager:
                return True
        return False

    def _get_sessions(self) -> Iterator[Session]:
        wm = windows.lookup(self.window)
        if wm is not None:
            view = self.window.active_view()
            if view is not None:
                for session in wm.sessions(view):
                    yield session

    def _make_item(self, max_details: Optional[int], parsed_uri: ParsedUri,
                   diagnostic: Diagnostic) -> Tuple[Union[Location, LocationLink], sublime.QuickPanelItem]:
        scheme, path = parsed_uri
        if scheme == "file":
            path = str(simple_project_path(map(Path, self.window.folders()), Path(path))) or path
        item = sublime.QuickPanelItem(self._make_trigger(path, diagnostic),
                                      self._make_details(max_details, diagnostic),
                                      "#{}".format(diagnostic_source(diagnostic)),
                                      DIAGNOSTIC_KIND_TUPLE[diagnostic_severity(diagnostic)])
        return diagnostic_location(parsed_uri, diagnostic), item

    def _diagnostic_items(self) -> Iterator[GotoDiagnosticItem]:
        raise NotImplementedError

    def _make_trigger(self, path: str, diagnostic: Diagnostic) -> str:
        raise NotImplementedError

    def _make_details(self, max_details: Optional[int], diagnostic: Diagnostic) -> Union[str, List[str]]:
        return ""

    def _get_on_modifier_keys(self) -> OnModifierKeysAcitonMap:
        # TODO: add {"primary"} to launch code actions
        return {}


class LspGotoDiagnosticForFileCommandBase(LspGotoDiagnosticCommandBase):
    def _diagnostic_items(self) -> Iterator[GotoDiagnosticItem]:
        if self._parsed_uri is None:
            return
        # TODO: should be user settings
        max_severity = GOTO_DIAGNOSTIC_SEVERITY_MAX_LEVEL
        max_details = GOTO_DIAGNOSTIC_MAX_DETAILS_LINES
        for session in self._get_sessions():
            weaksession = weakref.ref(session)
            for location, item in map(
                    functools.partial(self._make_item, max_details, self._parsed_uri),
                    filter(is_severity_included(max_severity),
                           session.diagnostics_manager.diagnostics_by_parsed_uri(self._parsed_uri))):
                yield (weaksession, location), item

    def _make_trigger(self, path: str, diagnostic: Diagnostic) -> str:
        lines = diagnostic["message"].splitlines()
        return "{}:{} {}".format(diagnostic["range"]["start"]["line"] + 1,
                                 diagnostic["range"]["start"]["character"] + 1, lines[0] if lines else "")

    def _make_details(self, max_details: Optional[int], diagnostic: Diagnostic) -> Union[str, List[str]]:
        return message_lines_truncated(max_details, diagnostic["message"].splitlines()[1:])

    _parsed_uri = None  # type: Optional[ParsedUri]


class LspGotoDiagnosticForDocumentUriCommand(LspGotoDiagnosticForFileCommandBase):
    def run(self, document_uri: DocumentUri) -> None:
        self._parsed_uri = parse_uri(document_uri)
        self._run()


class LspGotoDiagnosticCommand(LspGotoDiagnosticForFileCommandBase):
    def run(self) -> None:
        view = self.window.active_view()
        if view is None:
            return
        try:
            self._parsed_uri = parse_uri(uri_from_view(view))
        except MissingUriError:
            return
        self._run()


class LspGotoDiagnosticInProjectCommand(LspGotoDiagnosticCommandBase):
    def run(self) -> None:
        self._run()

    def _diagnostic_items(self) -> Iterator[GotoDiagnosticItem]:
        # TODO: should be user settings
        max_severity = GOTO_DIAGNOSTIC_SEVERITY_MAX_LEVEL
        max_details = GOTO_DIAGNOSTIC_MAX_DETAILS_LINES
        for session in self._get_sessions():
            weaksession = weakref.ref(session)
            for _, (location, item) in session.diagnostics_manager.filter_map_diagnostics_flat_async(
                    is_severity_included(max_severity), functools.partial(self._make_item, max_details)):
                yield (weaksession, location), item

    def _make_trigger(self, path: str, diagnostic: Diagnostic) -> str:
        return "{}:{}:{} ".format(path, diagnostic["range"]["start"]["line"] + 1,
                                  diagnostic["range"]["start"]["character"] + 1)

    def _make_details(self, max_details: Optional[int], diagnostic: Diagnostic) -> Union[str, List[str]]:
        return message_lines_truncated(max_details, diagnostic["message"].splitlines())

    def _get_on_modifier_keys(self) -> OnModifierKeysAcitonMap:
        # modifier key(s) from user settings?
        on_modifier_keys = super()._get_on_modifier_keys().copy()
        on_modifier_keys[frozenset({"alt"})] = self._run_goto_diagnostic_for_document_uri
        return on_modifier_keys

    def _run_goto_diagnostic_for_document_uri(self, view: sublime.View, session: Session, location: Union[Location,
                                                                                                          LocationLink],
                                              uri: DocumentUri, position: Position) -> None:
        self.window.run_command("lsp_goto_diagnostic_for_document_uri", dict(document_uri=uri))


def message_lines_truncated(max_details: Optional[int], lines: List[str]) -> List[str]:
    if max_details is not None and len(lines) > max_details:
        lines, rest = lines[:max_details], lines[max_details:]
        if rest:
            lines.append("...")
    return [html.escape(line) for line in lines] if list(filter(None, lines)) else []


def diagnostic_location(parsed_uri: ParsedUri, diagnostic: Diagnostic) -> Union[Location, LocationLink]:
    return dict(uri=unparse_uri(parsed_uri), range=diagnostic["range"])


def simple_project_path(project_folders: Iterable[Path], file_path: Path) -> Optional[Path]:
    """
    The simple project path of `/path/to/project/file` in the project `/path/to/project` is `project/file`.
    """
    folder_path = split_project_path(project_folders, file_path)
    if folder_path is None:
        return None
    folder, file = folder_path
    return folder.name / file


def resolve_simple_project_path(project_folders: Iterable[Path], file_path: Path) -> Optional[Path]:
    """
    The inverse of `simple_project_path()`.
    """
    parts = file_path.parts
    folder_name = parts[0]
    for folder in project_folders:
        if folder.name == folder_name:
            return folder / Path(*parts[1:])
    return None


def split_project_path(project_folders: Iterable[Path], file_path: Path) -> Optional[Tuple[Path, Path]]:
    abs_path = file_path.resolve()
    for folder in project_folders:
        try:
            rel_path = abs_path.relative_to(folder)
        except ValueError:
            continue
        return folder, rel_path
    return None
