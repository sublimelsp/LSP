from .core.diagnostics_manager import ParsedUri, is_severity_included
from .core.protocol import Diagnostic, DiagnosticSeverity, DocumentUri, Location, LocationLink, Position
from .core.registry import windows
from .core.sessions import Session
from .core.settings import userprefs
from .core.typing import Iterable, Iterator, List, Optional, Tuple, Union
from .core.url import parse_uri, unparse_uri
from .core.views import MissingUriError, diagnostic_severity, diagnostic_source, uri_from_view
from .locationpicker import EnhancedLocationPicker, OnModifierKeysAcitonMap
from collections import Counter, OrderedDict
from pathlib import Path
import functools
import sublime
import sublime_plugin
import weakref

DIAGNOSTIC_KIND_TUPLE = {
    DiagnosticSeverity.Error: (sublime.KIND_ID_COLOR_REDISH, "e", ""),
    DiagnosticSeverity.Warning: (sublime.KIND_ID_COLOR_YELLOWISH, "w", ""),
    DiagnosticSeverity.Information: (sublime.KIND_ID_COLOR_BLUISH, "i", ""),
    DiagnosticSeverity.Hint: (sublime.KIND_ID_COLOR_BLUISH, "h", ""),
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
            EnhancedLocationPicker(view,
                                   locations,
                                   items,
                                   side_by_side=False,
                                   on_modifier_keys=self._get_on_modifier_keys())

    def is_enabled(self) -> bool:
        for session in self._get_sessions():
            if session.diagnostics_manager:
                return True
        return False

    def _get_sessions(self) -> Iterator[Session]:
        raise NotImplementedError

    def _make_item(self, max_details: Optional[int], parsed_uri: ParsedUri,
                   diagnostic: Diagnostic) -> Tuple[Union[Location, LocationLink], sublime.QuickPanelItem]:
        item = sublime.QuickPanelItem(self._make_trigger(self._simple_project_path(parsed_uri), diagnostic),
                                      self._make_details(max_details,
                                                         diagnostic), "#{}".format(diagnostic_source(diagnostic)),
                                      DIAGNOSTIC_KIND_TUPLE[diagnostic_severity(diagnostic)])
        return diagnostic_location(parsed_uri, diagnostic), item

    def _simple_project_path(self, parsed_uri: ParsedUri) -> str:
        scheme, path = parsed_uri
        if scheme == "file":
            path = str(simple_project_path(map(Path, self.window.folders()), Path(path))) or path
        return path

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
    def _get_sessions(self) -> Iterator[Session]:
        wm = windows.lookup(self.window)
        if wm is not None:
            view = self.window.active_view()
            if view is not None:
                for session in wm.sessions(view):
                    yield session

    def _diagnostic_items(self) -> Iterator[GotoDiagnosticItem]:
        if self._parsed_uri is None:
            return
        max_severity = userprefs().diagnostics_panel_include_severity_level
        for session in self._get_sessions():
            weaksession = weakref.ref(session)
            for location, item in map(
                    functools.partial(self._make_item, 0, self._parsed_uri),
                    filter(is_severity_included(max_severity),
                           session.diagnostics_manager.diagnostics_by_parsed_uri(self._parsed_uri))):
                yield (weaksession, location), item

    def _make_trigger(self, path: str, diagnostic: Diagnostic) -> str:
        lines = diagnostic["message"].splitlines()
        return "{}:{} {}".format(diagnostic["range"]["start"]["line"] + 1,
                                 diagnostic["range"]["start"]["character"] + 1, lines[0] if lines else "")

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
    def _get_sessions(self) -> Iterator[Session]:
        wm = windows.lookup(self.window)
        if wm is not None:
            for session in wm._sessions:  # TODO: wm getter?
                yield session

    def run(self) -> None:
        self._run()

    def _diagnostic_items(self) -> Iterator[GotoDiagnosticItem]:
        max_severity = userprefs().diagnostics_panel_include_severity_level
        items_per_path = OrderedDict()  # type: OrderedDict[ParsedUri, List[Tuple[Union[Location, LocationLink], int]]]
        for session in self._get_sessions():
            weaksession = weakref.ref(session)
            for parsed_uri, location_item in session.diagnostics_manager.filter_map_diagnostics_flat_async(
                    is_severity_included(max_severity), _location_severity):
                seen = parsed_uri in items_per_path
                items_per_path.setdefault(parsed_uri, []).append(location_item)
                if not seen:
                    items_per_path.move_to_end(parsed_uri)
        for parsed_uri, location_items in items_per_path.items():
            location, _ = location_items[0]  # non-empty list
            counts = Counter(severity for _, severity in location_items)
            yield (weaksession, location), sublime.QuickPanelItem(
                self._simple_project_path(parsed_uri),
                "", "E: {}, W: {}".format(counts.get(DiagnosticSeverity.Error, 0),
                                          counts.get(DiagnosticSeverity.Warning,
                                                     0)), DIAGNOSTIC_KIND_TUPLE[min(counts)])

    def _get_on_modifier_keys(self) -> OnModifierKeysAcitonMap:
        on_modifier_keys = super()._get_on_modifier_keys().copy()
        on_modifier_keys[frozenset({"shift"})] = self._run_goto_diagnostic_for_document_uri
        return on_modifier_keys

    def _run_goto_diagnostic_for_document_uri(self, view: sublime.View, session: Session, location: Union[Location,
                                                                                                          LocationLink],
                                              uri: DocumentUri, position: Position) -> None:
        self.window.run_command("lsp_goto_diagnostic_for_document_uri", dict(document_uri=uri))


def _location_severity(parsed_uri: ParsedUri, diagnostic: Diagnostic) -> Tuple[Union[Location, LocationLink], int]:
    return diagnostic_location(parsed_uri, diagnostic), diagnostic_severity(diagnostic)


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
