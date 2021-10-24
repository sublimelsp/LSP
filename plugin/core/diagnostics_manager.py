from .protocol import Diagnostic, DiagnosticSeverity
from .settings import userprefs
from .typing import Callable, Iterator, List, Optional, Tuple
from .views import diagnostic_severity, format_diagnostic_for_panel
from collections import OrderedDict


class DiagnosticsManager(OrderedDict):
    # From the specs:
    #
    #   When a file changes it is the server’s responsibility to re-compute
    #   diagnostics and push them to the client. If the computed set is empty
    #   it has to push the empty array to clear former diagnostics. Newly
    #   pushed diagnostics always replace previously pushed diagnostics. There
    #   is no merging that happens on the client side.
    #
    # https://microsoft.github.io/language-server-protocol/specification#textDocument_publishDiagnostics

    def add_diagnostics(self, uri: str, diagnostics: List[Diagnostic]) -> None:
        if not diagnostics:
            # received "clear diagnostics" message for this uri
            self.pop(uri, None)
            return
        max_severity = userprefs().diagnostics_panel_include_severity_level
        self[uri] = (
            list(
                filter(
                    None,
                    (
                        format_diagnostic_for_panel(diagnostic)
                        for diagnostic in diagnostics
                        if diagnostic_severity(diagnostic) <= max_severity
                    ),
                )
            ),
            len(list(filter(has_severity(DiagnosticSeverity.Error), diagnostics))),
            len(list(filter(has_severity(DiagnosticSeverity.Warning), diagnostics))),
        )
        self.move_to_end(uri)  # maintain incoming order

    def diagnostics_panel_contributions(
        self,
    ) -> Iterator[Tuple[str, List[Tuple[str, Optional[int], Optional[str], Optional[str]]]]]:
        for uri, (contributions, _, _) in self.items():
            yield uri, contributions

    def sum_total_errors_and_warnings(self) -> Tuple[int, int]:
        return (
            sum(errors for _, errors, _ in self.values()),
            sum(warnings for _, _, warnings in self.values()),
        )


def has_severity(severity: int) -> Callable[[Diagnostic], bool]:
    def has_severity(diagnostic: Diagnostic) -> bool:
        return diagnostic_severity(diagnostic) == severity

    return has_severity
