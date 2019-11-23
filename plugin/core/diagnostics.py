from .logging import debug
from .url import uri_to_filename
from .protocol import Diagnostic, DiagnosticSeverity, Point
assert Diagnostic

try:
    import sublime
    from typing_extensions import Protocol
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert sublime
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass
    Protocol = object  # type: ignore


class DiagnosticsUI(Protocol):

    def update(self, file_name: str, config_name: str, diagnostics: 'Dict[str, Dict[str, List[Diagnostic]]]') -> None:
        ...

    def select(self, index: int) -> None:
        ...

    def deselect(self) -> None:
        ...


class DiagnosticsStorage(object):

    def __init__(self, updateable: 'Optional[DiagnosticsUI]') -> None:
        self._diagnostics = {}  # type: Dict[str, Dict[str, List[Diagnostic]]]
        self._updatable = updateable

    def get(self) -> 'Dict[str, Dict[str, List[Diagnostic]]]':
        return self._diagnostics

    def get_by_file(self, file_path: str) -> 'Dict[str, List[Diagnostic]]':
        return self._diagnostics.get(file_path, {})

    def update(self, file_path: str, client_name: str, diagnostics: 'List[Diagnostic]') -> bool:
        updated = False
        if diagnostics:
            file_diagnostics = self._diagnostics.setdefault(file_path, dict())
            file_diagnostics[client_name] = diagnostics
            updated = True
        else:
            if file_path in self._diagnostics:
                if client_name in self._diagnostics[file_path]:
                    updated = True
                    del self._diagnostics[file_path][client_name]
                if not self._diagnostics[file_path]:
                    del self._diagnostics[file_path]
        return updated

    def clear(self) -> None:
        for file_path in list(self._diagnostics):
            for client_name in list(self._diagnostics[file_path]):
                if self.update(file_path, client_name, []):
                    self.notify(file_path, client_name)

    def receive(self, client_name: str, update: dict) -> None:
        maybe_file_uri = update.get('uri')
        if maybe_file_uri is not None:
            file_path = uri_to_filename(maybe_file_uri)

            diagnostics = list(
                Diagnostic.from_lsp(item) for item in update.get('diagnostics', []))

            if self.update(file_path, client_name, diagnostics):
                self.notify(file_path, client_name)
        else:
            debug('missing uri in diagnostics update')

    def notify(self, file_path: str, client_name: str) -> None:
        if self._updatable:
            self._updatable.update(file_path, client_name, self._diagnostics)

    def remove(self, file_path: str, client_name: str) -> None:
        self.update(file_path, client_name, [])

    def select_next(self) -> None:
        if self._updatable:
            self._updatable.select(1)

    def select_previous(self) -> None:
        if self._updatable:
            self._updatable.select(-1)

    def select_none(self) -> None:
        if self._updatable:
            self._updatable.deselect()


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


class DiagnosticsCursor(DiagnosticsUpdateWalk):
    def __init__(self) -> None:
        self.file_diagnostic = None  # type: 'Optional[Tuple[str, Diagnostic]]'
        self._first_file_diagnostic = None  # type: 'Optional[Tuple[str, Diagnostic]]'
        self._last_file_diagnostic = None  # type: 'Optional[Tuple[str, Diagnostic]]'
        self._previous_file_diagnostic = None  # type: 'Optional[Tuple[str, Diagnostic]]'
        self._select_offset = 0
        self._debug_index = -1

    def select_offset(self, offset: int, file_path: 'Optional[str]' = None, point: 'Optional[Point]' = None) -> None:
        self._select_offset = offset
        self._select_file_path = file_path
        self._select_point = point

    def begin(self) -> None:
        self._found = False
        self._debug_index = -1
        self._first_file_diagnostic = None
        self._last_file_diagnostic = None
        self._nearest_file_diagnostic = None  # type: Optional[Tuple[str, Diagnostic]]
        self._previous_file_diagnostic = self.file_diagnostic
        self.file_diagnostic = None

    def begin_file(self, file_path: str) -> None:
        self._current_file_path = file_path

    def diagnostic(self, diagnostic: 'Diagnostic') -> None:
        if diagnostic.severity <= DiagnosticSeverity.Warning:
            if not self._found:
                if not self._first_file_diagnostic:
                    self._first_file_diagnostic = self._current_file_path, diagnostic

                if self._select_offset == -1:
                    if self._previous_file_diagnostic and diagnostic == self._previous_file_diagnostic[1]:
                        if self._last_file_diagnostic:
                            self.file_diagnostic = self._last_file_diagnostic
                            self._found = True

                elif self._select_offset == 1:
                    if self._last_file_diagnostic and self._previous_file_diagnostic and self._previous_file_diagnostic[
                            1] == self._last_file_diagnostic[1]:
                        self.file_diagnostic = self._current_file_path, diagnostic
                        self._found = True

                # update nearest candidate
                if not self._found and self._select_file_path and self._select_point and\
                        self._current_file_path == self._select_file_path:
                    self._update_nearest_candidate(diagnostic, self._select_point)

                self._last_file_diagnostic = self._current_file_path, diagnostic

    def _update_nearest_candidate(self, diagnostic: Diagnostic, point: Point) -> None:
        if self._select_offset == -1:
            if diagnostic.range.start.row < point.row:
                if not self._nearest_file_diagnostic or diagnostic.range.start.row > self._nearest_file_diagnostic[
                        1].range.start.row:
                    self._nearest_file_diagnostic = self._current_file_path, diagnostic
        elif self._select_offset == 1:
            if diagnostic.range.start.row > point.row:
                if not self._nearest_file_diagnostic or diagnostic.range.start.row < self._nearest_file_diagnostic[
                        1].range.start.row:
                    self._nearest_file_diagnostic = self._current_file_path, diagnostic

    def end(self) -> None:
        if not self.file_diagnostic:
            if self._select_offset == -1 and self._previous_file_diagnostic == self._first_file_diagnostic:
                self.file_diagnostic = self._last_file_diagnostic
            elif self._select_offset == 1 and self._previous_file_diagnostic == self._last_file_diagnostic:
                self.file_diagnostic = self._first_file_diagnostic
            elif self._nearest_file_diagnostic:  # a match before/after in the current file
                self.file_diagnostic = self._nearest_file_diagnostic

        self._select_offset = 0


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
