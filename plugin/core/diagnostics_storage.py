from .protocol import Diagnostic, DiagnosticSeverity, DocumentUri
from .typing import Callable, Iterator, List, Literal, Optional, Tuple, TypeVar
from .url import parse_uri
from .views import diagnostic_severity
from collections import OrderedDict
import functools
import operator
import sys

ParsedUri = Tuple[str, str]
SortOrder = Literal['asc', 'desc']
T = TypeVar('T')

# NOTE: OrderedDict can only be properly typed in Python >=3.8.
if sys.version_info >= (3, 8, 0):
    DiagnosticsStorageItems = OrderedDict[ParsedUri, List[Diagnostic]]
else:
    DiagnosticsStorageItems = OrderedDict


class DiagnosticsStorage(DiagnosticsStorageItems):
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

    def filter_map_diagnostics_async(
        self,
        pred: Callable[[Diagnostic], bool],
        f: Callable[[ParsedUri, Diagnostic], T],
        sort_order: Optional[SortOrder] = None
    ) -> Iterator[Tuple[ParsedUri, List[T]]]:
        """
        Yields `(uri, results)` items with `results` being a list of `f(diagnostic)` for each
        diagnostic for this `uri` with `pred(diagnostic) == True`, filtered by `bool(f(diagnostic))`.
        Only `uri`s with non-empty `results` are returned. Each `uri` is guaranteed to be yielded
        not more than once. Items and results are ordered as they came in from the server.
        """
        for uri, diagnostics in self.items():
            if sort_order:
                self._sort_by_location(diagnostics, sort_order)
            results = list(filter(None, map(functools.partial(f, uri), filter(pred, diagnostics))))
            if results:
                yield uri, results

    def filter_map_diagnostics_flat_async(
        self,
        pred: Callable[[Diagnostic], bool],
        f: Callable[[ParsedUri, Diagnostic], T],
        sort_order: Optional[SortOrder] = None
    ) -> Iterator[Tuple[ParsedUri, T]]:
        """
        Flattened variant of `filter_map_diagnostics_async()`. Yields `(uri, result)` items for each
        of the `result`s per `uri` instead. Each `uri` can be yielded more than once. Items are
        grouped by `uri` and each `uri` group is guaranteed to appear not more than once. Items are
        ordered as they came in from the server.
        """
        for uri, results in self.filter_map_diagnostics_async(pred, f, sort_order):
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

    def diagnostics_by_document_uri(
        self,
        document_uri: DocumentUri,
        sort_order: Optional[SortOrder] = None
    ) -> List[Diagnostic]:
        """
        Returns possibly empty list of diagnostic for `document_uri`.
        """
        diagnostics = self.get(parse_uri(document_uri), [])
        if sort_order:
            self._sort_by_location(diagnostics, sort_order)
        return diagnostics

    def diagnostics_by_parsed_uri(self, uri: ParsedUri, sort_order: Optional[SortOrder] = None) -> List[Diagnostic]:
        """
        Returns possibly empty list of diagnostic for `uri`.
        """
        diagnostics = self.get(uri, [])
        if sort_order:
            self._sort_by_location(diagnostics, sort_order)
        return diagnostics

    def _sort_by_location(self, diagnostics: List[Diagnostic], sort_order: SortOrder) -> None:
        diagnostics.sort(key=lambda d: operator.itemgetter('line', 'character')(d['range']['start']),
                         reverse=sort_order == 'desc')


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
