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

    def _update(self, file_path: str, client_name: str, diagnostics: 'List[Diagnostic]') -> bool:
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
                if self._update(file_path, client_name, []):
                    self._notify(file_path, client_name)

    def receive(self, client_name: str, update: dict) -> None:
        maybe_file_uri = update.get('uri')
        if maybe_file_uri is not None:
            file_path = uri_to_filename(maybe_file_uri)

            diagnostics = list(
                Diagnostic.from_lsp(item) for item in update.get('diagnostics', []))

            if self._update(file_path, client_name, diagnostics):
                self._notify(file_path, client_name)
        else:
            debug('missing uri in diagnostics update')

    def _notify(self, file_path: str, client_name: str) -> None:
        if self._updatable:
            self._updatable.update(file_path, client_name, self._diagnostics)

    def remove(self, file_path: str, client_name: str) -> None:
        self._update(file_path, client_name, [])

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


CURSOR_FORWARD = 1
CURSOR_BACKWARD = -1


class FromPositionWalk(DiagnosticsUpdateWalk):
    def __init__(self, cursor: 'DiagnosticsCursor', file_path: str, point: Point, direction: int) -> None:
        self.file_path = file_path
        self.point = point
        self._cursor = cursor
        self._direction = direction
        self.file_diagnostic = None  # type: Optional[Tuple[str, Diagnostic]]
        self._first_file_diagnostic = None  # type: Optional[Tuple[str, Diagnostic]]
        self._nearest_file_diagnostic = None  # type: Optional[Tuple[str, Diagnostic]]
        self._previous_file_diagnostic = None  # type: Optional[Tuple[str, Diagnostic]]

    def begin_file(self, file_path: str) -> None:
        self._current_file_path = file_path

    def diagnostic(self, diagnostic: 'Diagnostic') -> None:
        if diagnostic.severity <= DiagnosticSeverity.Warning:
            if not self._first_file_diagnostic:
                self._first_file_diagnostic = self._current_file_path, diagnostic

            if self._direction == CURSOR_FORWARD:
                if self._current_file_path == self.file_path:
                    self._take_if_nearer_forward(diagnostic)
            else:
                if self._current_file_path == self.file_path:
                    self._take_if_nearer_backward(diagnostic)
                    self._last_before_file_diagnostic = self._previous_file_diagnostic
                self._previous_file_diagnostic = self._current_file_path, diagnostic

    def _take_if_nearer_forward(self, diagnostic: Diagnostic) -> None:
        if diagnostic.range.start.row > self.point.row:
            if not self._nearest_file_diagnostic or diagnostic.range.start.row < self._nearest_file_diagnostic[
                    1].range.start.row:
                self._nearest_file_diagnostic = self._current_file_path, diagnostic

    def _take_if_nearer_backward(self, diagnostic: Diagnostic) -> None:
        if diagnostic.range.start.row < self.point.row:
            if not self._nearest_file_diagnostic or diagnostic.range.start.row > self._nearest_file_diagnostic[
                    1].range.start.row:
                self._nearest_file_diagnostic = self._current_file_path, diagnostic

    def end(self) -> None:
        if self._nearest_file_diagnostic:
            self._cursor.set_value(self._nearest_file_diagnostic)
        else:
            if self._direction == CURSOR_FORWARD:
                self._cursor.set_value(self._first_file_diagnostic)
            else:
                self._cursor.set_value(self._last_before_file_diagnostic)


class DiagnosticsUpdatedWalk(DiagnosticsUpdateWalk):

    def __init__(self, cursor: 'DiagnosticsCursor', file_path: str, diagnostic: Diagnostic) -> None:
        self._file_path = file_path
        self._diagnostic = diagnostic
        self._cursor = cursor
        self.file_diagnostic = None  # type: Optional[Tuple[str, Diagnostic]]

    def begin_file(self, file_path: str) -> None:
        self._is_same_file = self._file_path == file_path

    def diagnostic(self, diagnostic: 'Diagnostic') -> None:
        if self._is_same_file:
            if diagnostic == self._diagnostic:
                self.file_diagnostic = self._file_path, diagnostic

    def end(self) -> None:
        self._cursor.set_value(self.file_diagnostic)


class FromDiagnosticWalk(DiagnosticsUpdateWalk):
    def __init__(self, cursor: 'DiagnosticsCursor', direction: int, file_path: str, diagnostic: Diagnostic) -> None:
        self._file_path = file_path
        self._diagnostic = diagnostic
        self._direction = direction
        self.file_diagnostic = None  # type: Optional[Tuple[str, Diagnostic]]
        self._cursor = cursor
        self._first_file_diagnostic = None  # type: Optional[Tuple[str, Diagnostic]]
        self._previous_file_diagnostic = None  # type: Optional[Tuple[str, Diagnostic]]
        self._take_next = False

    def begin_file(self, file_path: str) -> None:
        self._current_file_path = file_path

    def diagnostic(self, diagnostic: 'Diagnostic') -> None:
        if diagnostic.severity <= DiagnosticSeverity.Warning:
            if self._direction == CURSOR_FORWARD:
                if self._take_next:
                    self.file_diagnostic = self._current_file_path, diagnostic
                    self._take_next = False
                elif diagnostic == self._diagnostic and self._current_file_path == self._file_path:
                    self._take_next = True
            else:
                if self._current_file_path == self._file_path and self._diagnostic == diagnostic:
                    if self._previous_file_diagnostic:
                        self.file_diagnostic = self._previous_file_diagnostic
                self._previous_file_diagnostic = self._current_file_path, diagnostic

    def end(self) -> None:
        if self.file_diagnostic:
            self._cursor.set_value(self.file_diagnostic)
        else:
            if self._direction == CURSOR_BACKWARD:
                self._cursor.set_value(self._previous_file_diagnostic)
            else:
                self._cursor.set_value((self._file_path, self._diagnostic))


class TakeFirstDiagnosticWalk(DiagnosticsUpdateWalk):

    def __init__(self, cursor: 'DiagnosticsCursor', direction: int) -> None:
        self._cursor = cursor
        self._file_diagnostic = None  # type: 'Optional[Tuple[str, Diagnostic]]'
        self._direction = direction

    def begin_file(self, file_path: str) -> None:
        self._current_file_path = file_path

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        if diagnostic.severity <= DiagnosticSeverity.Warning:
            if self._direction == CURSOR_FORWARD:
                if self._file_diagnostic is None:
                    self._file_diagnostic = self._current_file_path, diagnostic
            else:
                self._file_diagnostic = self._current_file_path, diagnostic

    def end(self) -> None:
        self._cursor.set_value(self._file_diagnostic)


class DiagnosticsCursor(DiagnosticsUpdateWalk):

    def __init__(self) -> None:
        self._file_diagnostic = None  # type: 'Optional[Tuple[str, Diagnostic]]'

    @property
    def has_value(self) -> bool:
        return self._file_diagnostic is not None

    def set_value(self, file_diagnostic: 'Optional[Tuple[str, Diagnostic]]') -> None:
        self._file_diagnostic = file_diagnostic

    @property
    def value(self) -> 'Optional[Tuple[str, Diagnostic]]':
        return self._file_diagnostic

    def from_position(self, direction: int, file_path: 'Optional[str]' = None,
                      point: 'Optional[Point]' = None) -> DiagnosticsUpdateWalk:
        if file_path and point:
            return FromPositionWalk(self, file_path, point, direction)
        else:
            return TakeFirstDiagnosticWalk(self, direction)

    def from_diagnostic(self, direction: int) -> DiagnosticsUpdateWalk:
        assert self._file_diagnostic
        return FromDiagnosticWalk(self, direction, *self._file_diagnostic)

    def update(self) -> DiagnosticsUpdateWalk:
        assert self._file_diagnostic
        return DiagnosticsUpdatedWalk(self, *self._file_diagnostic)


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
