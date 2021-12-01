from .protocol import Diagnostic, DiagnosticSeverity, DocumentUri
from .settings import userprefs
from .typing import Callable, Iterator, List, Tuple, TypeVar
from .url import parse_uri
from .views import diagnostic_severity
from collections import OrderedDict
import functools

ParsedUri = Tuple[str, str]
T = TypeVar('T')


def by_location(diagnostic: Diagnostic) -> Tuple[int, int]:
    position = diagnostic.get("range", {})["start"]
    return position["line"], position["character"]


def by_severity(diagnostic: Diagnostic) -> Tuple[int, int, int]:
    severity = diagnostic.get("severity", DiagnosticSeverity.Hint + 1)
    position = diagnostic.get("range", {})["start"]
    return severity, position["line"], position["character"]


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

    def add_diagnostics_async(self, document_uri: DocumentUri, diagnostics: List[Diagnostic]) -> None:
        """
        Add `diagnostics` for `document_uri` to the store, replacing previously received `diagnoscis`
        for this `document_uri`. If `diagnostics` is the empty list, `document_uri` is removed from
        the store. The item received is moved to the end of the store.
        """
        uri = parse_uri(document_uri)
        if not diagnostics:
            # received "clear diagnostics" message for this uri
            self.pop(uri, None)
            return
        self[uri] = diagnostics
        self.move_to_end(uri)  # maintain incoming order

    def sorted_diagnostics(self, uri: ParsedUri) -> List[Diagnostic]:
        """
        Sort diagnostics for a given URI ordered as configured by the `diagnostics_sort_order` setting.
        """
        sort_order = userprefs().diagnostics_sort_order
        if sort_order == "location":
            return sorted(self[uri], key=by_location)
        elif sort_order == "severity":
            return sorted(self[uri], key=by_severity)
        else:  # "none"
            return self[uri]

    def filter_map_diagnostics_async(self, pred: Callable[[Diagnostic], bool],
                                     f: Callable[[ParsedUri, Diagnostic], T]) -> Iterator[Tuple[ParsedUri, List[T]]]:
        """
        Yields `(uri, results)` items with `results` being a list of `f(diagnostic)` for each
        diagnostic for this `uri` with `pred(diagnostic) == True`, filtered by `bool(f(diagnostic))`.
        Only `uri`s with non-empty `results` are returned. Each `uri` is guaranteed to be yielded
        not more than once. Items are ordered as they came in from the server and results per item are
        ordered as configured by the `diagnostics_sort_order` setting.
        """
        for uri in self.keys():
            diagnostics = self.sorted_diagnostics(uri)
            results = list(filter(None, map(functools.partial(f, uri), filter(pred, diagnostics))))  # type: List[T]
            if results:
                yield uri, results

    def filter_map_diagnostics_flat_async(self, pred: Callable[[Diagnostic], bool],
                                          f: Callable[[ParsedUri, Diagnostic], T]) -> Iterator[Tuple[ParsedUri, T]]:
        """
        Flattened variant of `filter_map_diagnostics_async()`. Yields `(uri, result)` items for each
        of the `result`s per `uri` instead. Each `uri` can be yielded more than once. Items are
        grouped by `uri` and each `uri` group is guaranteed to appear not more than once. Items are
        ordered as they came in from the server.
        """
        for uri, results in self.filter_map_diagnostics_async(pred, f):
            for result in results:
                yield uri, result

    def sum_total_errors_and_warnings_async(self) -> Tuple[int, int]:
        """
        Returns `(total_errors, total_warnings)` count of all diagnostics currently in store.
        """
        return (
            sum(map(severity_count(DiagnosticSeverity.Error), self.values())),
            sum(map(severity_count(DiagnosticSeverity.Warning), self.values())),
        )

    def diagnostics_by_document_uri(self, document_uri: DocumentUri) -> List[Diagnostic]:
        """
        Returns possibly empty list of diagnostic for `document_uri`.
        """
        return self.get(parse_uri(document_uri), [])

    def diagnostics_by_parsed_uri(self, uri: ParsedUri) -> List[Diagnostic]:
        """
        Returns possibly empty list of diagnostic for `uri`.
        Results are ordered as configured by the `diagnostics_sort_order` setting.
        """
        return self.sorted_diagnostics(uri) if uri in self else []


def severity_count(severity: int) -> Callable[[List[Diagnostic]], int]:
    def severity_count(diagnostics: List[Diagnostic]) -> int:
        return len(list(filter(has_severity(severity), diagnostics)))

    return severity_count


def has_severity(severity: int) -> Callable[[Diagnostic], bool]:
    def has_severity(diagnostic: Diagnostic) -> bool:
        return diagnostic_severity(diagnostic) == severity

    return has_severity


def is_severity_included(max_severity: int) -> Callable[[Diagnostic], bool]:
    def severity_included(diagnostic: Diagnostic) -> bool:
        return diagnostic_severity(diagnostic) <= max_severity

    return severity_included
