from .panels import ensure_panel
from .protocol import Diagnostic
from .protocol import Point
from .sessions import SessionBufferProtocol
from .typing import List, Tuple, Callable, Optional, Iterable
import sublime


def ensure_diagnostics_panel(window: sublime.Window) -> Optional[sublime.View]:
    return ensure_panel(window, "diagnostics", r"^(.*):$", r"^\s*(\d+):(\d+)",
                        "Packages/LSP/Syntaxes/Diagnostics.sublime-syntax")


class DiagnosticsUpdateWalk(object):

    def begin(self) -> None:
        pass

    def begin_file(self, file_path: str) -> None:
        pass

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        pass

    def end_file(self, file_path: str) -> None:
        pass

    def end(self) -> None:
        pass


CURSOR_FORWARD = 1
CURSOR_BACKWARD = -1


class DiagnosticCursorWalk(DiagnosticsUpdateWalk):
    def __init__(self, cursor: 'DiagnosticsCursor', direction: int = 0) -> None:
        self._cursor = cursor
        self._direction = direction
        self._current_file_path = ""
        self._candidate = None  # type: Optional[Tuple[str, Diagnostic]]

    def begin_file(self, file_path: str) -> None:
        self._current_file_path = file_path

    def _meets_max_severity(self, diagnostic: Diagnostic) -> bool:
        return diagnostic.severity <= self._cursor.max_severity_level

    def _take_candidate(self, diagnostic: Diagnostic) -> None:
        self._candidate = self._current_file_path, diagnostic

    def end(self) -> None:
        self._cursor.set_value(self._candidate)


class FromPositionWalk(DiagnosticCursorWalk):
    def __init__(self, cursor: 'DiagnosticsCursor', file_path: str, point: Point, direction: int) -> None:
        super().__init__(cursor, direction)
        self._first = None  # type: Optional[Tuple[str, Diagnostic]]
        self._previous = None  # type: Optional[Tuple[str, Diagnostic]]

        # position-specific
        self._file_path = file_path
        self._point = point
        self._first_after_file = None  # type: Optional[Tuple[str, Diagnostic]]
        self._last_before_file = None  # type: Optional[Tuple[str, Diagnostic]]

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        if self._meets_max_severity(diagnostic):
            if not self._first:
                self._first = self._current_file_path, diagnostic

            if self._current_file_path == self._file_path:
                if self._direction == CURSOR_FORWARD:
                    self._take_if_nearer_forward(diagnostic)
                else:
                    self._take_if_nearer_backward(diagnostic)
                    self._set_last_before_file(diagnostic)
            else:
                if self._direction == CURSOR_FORWARD:
                    self._set_first_after_file(diagnostic)

            self._previous = self._current_file_path, diagnostic

    def _take_if_nearer_forward(self, diagnostic: Diagnostic) -> None:
        if diagnostic.range.start.row > self._point.row:
            if not self._candidate:
                self._take_candidate(diagnostic)
            else:
                candidate_start_row = self._candidate[1].range.start.row
                if diagnostic.range.start.row < candidate_start_row:
                    self._take_candidate(diagnostic)

    def _take_if_nearer_backward(self, diagnostic: Diagnostic) -> None:
        if diagnostic.range.start.row < self._point.row:
            if not self._candidate:
                self._take_candidate(diagnostic)
            else:
                candidate_start_row = self._candidate[1].range.start.row
                if diagnostic.range.start.row > candidate_start_row:
                    self._take_candidate(diagnostic)

    def _set_last_before_file(self, diagnostic: Diagnostic) -> None:
        if not self._last_before_file and self._previous:
            if self._previous[0] != self._current_file_path:
                self._last_before_file = self._previous

    def _set_first_after_file(self, diagnostic: Diagnostic) -> None:
        if not self._first_after_file:
            if self._previous and self._previous[0] == self._file_path:
                self._first_after_file = self._current_file_path, diagnostic

    def end(self) -> None:
        if self._candidate:
            self._cursor.set_value(self._candidate)
        else:
            if self._direction == CURSOR_FORWARD:
                self._cursor.set_value(self._first_after_file or self._first)
            else:
                self._cursor.set_value(self._last_before_file or self._previous)


class FromDiagnosticWalk(DiagnosticCursorWalk):
    def __init__(self, cursor: 'DiagnosticsCursor', direction: int) -> None:
        super().__init__(cursor, direction)

        self._first = None  # type: Optional[Tuple[str, Diagnostic]]
        self._previous = None  # type: Optional[Tuple[str, Diagnostic]]

        assert cursor.value
        self._file_path, self._diagnostic = cursor.value
        self._take_next = False

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        if self._meets_max_severity(diagnostic):

            if self._direction == CURSOR_FORWARD:
                if not self._first:
                    self._first = self._current_file_path, diagnostic

                if self._take_next:
                    self._take_candidate(diagnostic)
                    self._take_next = False
                elif diagnostic == self._diagnostic and self._current_file_path == self._file_path:
                    self._take_next = True
            else:
                if self._current_file_path == self._file_path and self._diagnostic == diagnostic:
                    if self._previous:
                        self._candidate = self._previous
                self._previous = self._current_file_path, diagnostic

    def end(self) -> None:
        if self._candidate:
            self._cursor.set_value(self._candidate)
        else:
            if self._direction == CURSOR_FORWARD:
                self._cursor.set_value(self._first)
            else:
                self._cursor.set_value(self._previous)


class TakeFirstDiagnosticWalk(DiagnosticCursorWalk):
    def diagnostic(self, diagnostic: Diagnostic) -> None:
        if self._meets_max_severity(diagnostic):
            if self._direction == CURSOR_FORWARD:
                if self._candidate is None:
                    self._take_candidate(diagnostic)
            else:
                self._take_candidate(diagnostic)


class DiagnosticsUpdatedWalk(DiagnosticCursorWalk):
    def diagnostic(self, diagnostic: Diagnostic) -> None:
        if self._cursor.value:
            if self._current_file_path == self._cursor.value[0]:
                if diagnostic == self._cursor.value[1]:
                    self._take_candidate(diagnostic)


class DiagnosticsCursor(object):
    def __init__(self, show_diagnostics_severity_level: int = 2) -> None:
        self._file_diagnostic = None  # type: Optional[Tuple[str, Diagnostic]]
        self.max_severity_level = show_diagnostics_severity_level

    @property
    def has_value(self) -> bool:
        return self._file_diagnostic is not None

    def set_value(self, file_diagnostic: Optional[Tuple[str, Diagnostic]]) -> None:
        self._file_diagnostic = file_diagnostic

    @property
    def value(self) -> Optional[Tuple[str, Diagnostic]]:
        return self._file_diagnostic

    def from_position(self, direction: int, file_path: Optional[str] = None,
                      point: Optional[Point] = None) -> DiagnosticsUpdateWalk:
        if file_path and point:
            return FromPositionWalk(self, file_path, point, direction)
        else:
            return TakeFirstDiagnosticWalk(self, direction)

    def from_diagnostic(self, direction: int) -> DiagnosticsUpdateWalk:
        assert self._file_diagnostic
        return FromDiagnosticWalk(self, direction)

    def update(self) -> DiagnosticsUpdateWalk:
        assert self._file_diagnostic
        return DiagnosticsUpdatedWalk(self)


class DiagnosticsWalker(object):
    """ Iterate over diagnostics structure"""

    def __init__(self, subs: List[DiagnosticsUpdateWalk]) -> None:
        self._subscribers = subs

    def walk(
        self,
        diagnostics_by_file: Iterable[Tuple[str, Iterable[Tuple[SessionBufferProtocol, List[Diagnostic]]]]]
    ) -> None:
        self.invoke_each(lambda w: w.begin())
        for file_path, source_diagnostics in diagnostics_by_file:
            self.invoke_each(lambda w: w.begin_file(file_path))
            for _, diagnostics in source_diagnostics:
                for diagnostic in diagnostics:
                    self.invoke_each(lambda w: w.diagnostic(diagnostic))
            self.invoke_each(lambda w: w.end_file(file_path))
        self.invoke_each(lambda w: w.end())

    def invoke_each(self, func: Callable[[DiagnosticsUpdateWalk], None]) -> None:
        for sub in self._subscribers:
            func(sub)
