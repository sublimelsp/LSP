from .core.diagnostics_storage import ParsedUri, is_severity_included
from .core.protocol import Diagnostic, DocumentUri, DiagnosticSeverity, Location
from .core.registry import windows
from .core.sessions import Session
from .core.settings import userprefs
from .core.types import ClientConfig
from .core.typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple, Union
from .core.url import parse_uri, unparse_uri
from .core.views import DIAGNOSTIC_KINDS
from .core.views import MissingUriError, uri_from_view, get_uri_and_position_from_location, to_encoded_filename
from .core.views import format_diagnostic_for_html
from .core.views import diagnostic_severity, format_diagnostic_source_and_code, format_severity
from abc import ABCMeta
from abc import abstractmethod
from collections import Counter, OrderedDict
from pathlib import Path
import functools
import sublime
import sublime_plugin


PREVIEW_PANE_CSS = """
    .diagnostics {padding: 0.5em}
    .diagnostics a {color: var(--bluish)}
    .diagnostics.error {background-color: color(var(--redish) alpha(0.25))}
    .diagnostics.warning {background-color: color(var(--yellowish) alpha(0.25))}
    .diagnostics.info {background-color: color(var(--bluish) alpha(0.25))}
    .diagnostics.hint {background-color: color(var(--bluish) alpha(0.25))}
    """


def get_sessions(window: sublime.Window) -> Iterator[Session]:
    wm = windows.lookup(window)
    if wm is not None:
        yield from wm._sessions


class LspGotoDiagnosticCommand(sublime_plugin.WindowCommand):
    def run(self, uri: Optional[DocumentUri], diagnostic: Optional[dict]) -> None:  # type: ignore
        pass

    def is_enabled(self, uri: Optional[DocumentUri] = None, diagnostic: Optional[dict] = None) -> bool:  # type: ignore
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

    def input(self, args: dict) -> Optional[sublime_plugin.CommandInputHandler]:
        uri, diagnostic = args.get("uri"), args.get("diagnostic")
        view = self.window.active_view()
        if view is None:
            return None
        if not uri:
            return DiagnosticUriInputHandler(self.window, view)
        if uri == "$view_uri":
            try:
                uri = uri_from_view(view)
                return DiagnosticUriInputHandler(self.window, view, uri)
            except MissingUriError:
                return None
        if not diagnostic:
            return DiagnosticInputHandler(self.window, view, uri)
        return None

    def input_description(self) -> str:
        return "Goto Diagnostic"


ListItemsReturn = Union[List[str], Tuple[List[str], int], List[Tuple[str, Any]], Tuple[List[Tuple[str, Any]], int],
                        List[sublime.ListInputItem], Tuple[List[sublime.ListInputItem], int]]


class PreselectedListInputHandler(sublime_plugin.ListInputHandler, metaclass=ABCMeta):
    """
    Similar to ListInputHandler, but allows to preselect a value like some of the input overlays in Sublime Merge.
    Inspired by https://github.com/sublimehq/sublime_text/issues/5507.

    Subclasses of PreselectedListInputHandler must not implement the `list_items` method, but instead `_list_items`,
    i.e. just prepend an underscore to the regular `list_items`.

    When an instance of PreselectedListInputHandler is created, it must be given the window as an argument.
    An optional second argument `initial_value` can be provided to preselect a value.
    """

    _window = None  # type: Optional[sublime.Window]
    _initial_value = None  # type: Optional[Union[str, sublime.ListInputItem]]
    _preselect = False

    def __init__(
        self, window: sublime.Window, initial_value: Optional[Union[str, sublime.ListInputItem]] = None
    ) -> None:
        super().__init__()
        if initial_value is not None:
            self._window = window
            self._initial_value = initial_value
            self._preselect = True

    def list_items(self) -> ListItemsReturn:
        if self._preselect and self._initial_value is not None and self._window is not None:
            self._preselect = False
            sublime.set_timeout(functools.partial(self._window.run_command, 'select'))
            return [self._initial_value], 0  # pyright: ignore[reportGeneralTypeIssues]
        else:
            return self._list_items()

    @abstractmethod
    def _list_items(self) -> ListItemsReturn:
        raise NotImplementedError()


class DiagnosticUriInputHandler(PreselectedListInputHandler):
    _preview = None  # type: Optional[sublime.View]
    uri = None  # Optional[DocumentUri]

    def __init__(self, window: sublime.Window, view: sublime.View, initial_value: Optional[DocumentUri] = None) -> None:
        super().__init__(window, initial_value)
        self.window = window
        self.view = view

    def name(self) -> str:
        return "uri"

    def _list_items(self) -> Tuple[List[sublime.ListInputItem], int]:
        max_severity = userprefs().diagnostics_panel_include_severity_level
        # collect severities and location of first diagnostic per uri
        severities_per_path = OrderedDict()  # type: OrderedDict[ParsedUri, List[DiagnosticSeverity]]
        self.first_locations = dict()  # type: Dict[ParsedUri, Tuple[Session, Location]]
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
            text = "{}: {}".format(format_severity(min(counts)), self._simple_project_path(parsed_uri))
            annotation = "E: {}, W: {}".format(counts.get(DiagnosticSeverity.Error, 0),
                                               counts.get(DiagnosticSeverity.Warning, 0))
            kind = DIAGNOSTIC_KINDS[min(counts)]
            uri = unparse_uri(parsed_uri)
            if uri == self.uri:
                selected = i  # restore selection after coming back from diagnostics list
            list_items.append(sublime.ListInputItem(text, uri, annotation=annotation, kind=kind))
        return list_items, selected

    def placeholder(self) -> str:
        return "Select file"

    def next_input(self, args: dict) -> Optional[sublime_plugin.CommandInputHandler]:
        uri, diagnostic = args.get("uri"), args.get("diagnostic")
        if uri is None:
            return None
        if diagnostic is None:
            self._preview = None
            return DiagnosticInputHandler(self.window, self.view, uri)
        return sublime_plugin.BackInputHandler()  # type: ignore

    def confirm(self, value: Optional[DocumentUri]) -> None:
        self.uri = value

    def description(self, value: DocumentUri, text: str) -> str:
        return self._project_path(parse_uri(value))

    def cancel(self) -> None:
        if self._preview is not None and self._preview.sheet().is_transient():
            self._preview.close()
        self.window.focus_view(self.view)

    def preview(self, value: Optional[DocumentUri]) -> str:
        if not value or not hasattr(self, 'first_locations'):
            return ""
        parsed_uri = parse_uri(value)
        session, location = self.first_locations[parsed_uri]
        scheme, _ = parsed_uri
        if scheme == "file":
            self._preview = open_location(session, location, flags=sublime.TRANSIENT)
        return ""

    def _simple_project_path(self, parsed_uri: ParsedUri) -> str:
        scheme, path = parsed_uri
        if scheme == "file":
            path = str(simple_project_path(map(Path, self.window.folders()), Path(path))) or path
        return path

    def _project_path(self, parsed_uri: ParsedUri) -> str:
        scheme, path = parsed_uri
        if scheme == "file":
            path = str(project_path(map(Path, self.window.folders()), Path(path))) or path
        return path


class DiagnosticInputHandler(sublime_plugin.ListInputHandler):
    _preview = None  # type: Optional[sublime.View]

    def __init__(self, window: sublime.Window, view: sublime.View, uri: DocumentUri) -> None:
        self.window = window
        self.view = view
        self.sessions = list(get_sessions(window))
        self.parsed_uri = parse_uri(uri)

    def name(self) -> str:
        return "diagnostic"

    def list_items(self) -> List[sublime.ListInputItem]:
        list_items = []
        max_severity = userprefs().diagnostics_panel_include_severity_level
        for i, session in enumerate(self.sessions):
            for diagnostic in filter(is_severity_included(max_severity),
                                     session.diagnostics.diagnostics_by_parsed_uri(self.parsed_uri)):
                lines = diagnostic["message"].splitlines()
                first_line = lines[0] if lines else ""
                if len(lines) > 1:
                    first_line += " …"
                text = "{}: {}".format(format_severity(diagnostic_severity(diagnostic)), first_line)
                annotation = format_diagnostic_source_and_code(diagnostic)
                kind = DIAGNOSTIC_KINDS[diagnostic_severity(diagnostic)]
                list_items.append(sublime.ListInputItem(text, (i, diagnostic), annotation=annotation, kind=kind))
        return list_items

    def placeholder(self) -> str:
        return "Select diagnostic"

    def next_input(self, args: dict) -> Optional[sublime_plugin.CommandInputHandler]:
        return None if args.get("diagnostic") else sublime_plugin.BackInputHandler()  # type: ignore

    def confirm(self, value: Optional[Tuple[int, Diagnostic]]) -> None:
        if not value:
            return
        i, diagnostic = value
        session = self.sessions[i]
        location = self._get_location(diagnostic)
        scheme, _ = self.parsed_uri
        if scheme == "file":
            open_location(session, self._get_location(diagnostic))
        else:
            sublime.set_timeout_async(functools.partial(session.open_location_async, location))

    def cancel(self) -> None:
        if self._preview is not None and self._preview.sheet().is_transient():
            self._preview.close()
        self.window.focus_view(self.view)

    def preview(self, value: Optional[Tuple[int, Diagnostic]]) -> Union[str, sublime.Html]:
        if not value:
            return ""
        i, diagnostic = value
        session = self.sessions[i]
        base_dir = None
        scheme, path = self.parsed_uri
        if scheme == "file":
            self._preview = open_location(session, self._get_location(diagnostic), flags=sublime.TRANSIENT)
            base_dir = project_base_dir(map(Path, self.window.folders()), Path(path))
        return diagnostic_html(self.view, session.config, truncate_message(diagnostic), base_dir)

    def _get_location(self, diagnostic: Diagnostic) -> Location:
        return diagnostic_location(self.parsed_uri, diagnostic)


def diagnostic_location(parsed_uri: ParsedUri, diagnostic: Diagnostic) -> Location:
    return {
        'uri': unparse_uri(parsed_uri),
        'range': diagnostic["range"]
    }


def open_location(session: Session, location: Location, flags: int = 0, group: int = -1) -> sublime.View:
    uri, position = get_uri_and_position_from_location(location)
    file_name = to_encoded_filename(session.config.map_server_uri_to_client_path(uri), position)
    return session.window.open_file(file_name, flags=flags | sublime.ENCODED_POSITION, group=group)


def diagnostic_html(view: sublime.View, config: ClientConfig, diagnostic: Diagnostic,
                    base_dir: Optional[Path]) -> sublime.Html:
    content = format_diagnostic_for_html(view, config, truncate_message(diagnostic),
                                         None if base_dir is None else str(base_dir))
    return sublime.Html('<style>{}</style><div class="diagnostics {}">{}</div>'.format(
        PREVIEW_PANE_CSS, format_severity(diagnostic_severity(diagnostic)), content))


def truncate_message(diagnostic: Diagnostic, max_lines: int = 6) -> Diagnostic:
    lines = diagnostic["message"].splitlines()
    if len(lines) <= max_lines:
        return diagnostic
    diagnostic = diagnostic.copy()
    diagnostic["message"] = "\n".join(lines[:max_lines - 1]) + " …\n"
    return diagnostic


def project_path(project_folders: Iterable[Path], file_path: Path) -> Optional[Path]:
    """
    The project path of `/path/to/project/file` in the project `/path/to/project` is `file`.
    """
    folder_path = split_project_path(project_folders, file_path)
    if folder_path is None:
        return None
    _, file = folder_path
    return file


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


def project_base_dir(project_folders: Iterable[Path], file_path: Path) -> Optional[Path]:
    """
    The project base dir of `/path/to/project/file` in the project `/path/to/project` is `/path/to`.
    """
    folder_path = split_project_path(project_folders, file_path)
    if folder_path is None:
        return None
    folder, _ = folder_path
    return folder.parent


def split_project_path(project_folders: Iterable[Path], file_path: Path) -> Optional[Tuple[Path, Path]]:
    abs_path = file_path.resolve()
    for folder in project_folders:
        try:
            rel_path = abs_path.relative_to(folder)
        except ValueError:
            continue
        return folder, rel_path
    return None
