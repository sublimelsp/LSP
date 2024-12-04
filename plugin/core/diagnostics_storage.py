from __future__ import annotations
from .protocol import Diagnostic
from .protocol import DiagnosticSeverity
from .protocol import DocumentUri
from .protocol import Point
from .url import normalize_uri
from .views import diagnostic_severity
from collections.abc import MutableMapping
from typing import Callable, Iterator, Tuple, TypeVar
import itertools
import functools

ParsedUri = Tuple[str, str]
T = TypeVar('T')


class DiagnosticsStorage(MutableMapping):

    def __init__(self) -> None:
        super().__init__()
        self._d: dict[tuple[DocumentUri, str], list[Diagnostic]] = dict()
        self._identifiers = {''}
        self._uris: set[DocumentUri] = set()

    def __getitem__(self, key: DocumentUri, /) -> list[Diagnostic]:
        uri = normalize_uri(key)
        return sorted(
            itertools.chain.from_iterable(self._d.get((uri, identifier), []) for identifier in self._identifiers),
            key=lambda diagnostic: Point.from_lsp(diagnostic['range']['start'])
        )

    def __setitem__(self, key: DocumentUri | tuple[DocumentUri, str], value: list[Diagnostic], /) -> None:
        uri, identifier = (normalize_uri(key), '') if isinstance(key, DocumentUri) else (normalize_uri(key[0]), key[1])
        if identifier not in self._identifiers:
            raise ValueError(f'identifier {identifier} must be registered first')
        if value:
            self._uris.add(uri)
            self._d[(uri, identifier)] = value
        else:
            self._uris.discard(uri)
            self._d.pop((uri, identifier), None)

    def __delitem__(self, key: DocumentUri, /) -> None:
        uri = normalize_uri(key)
        self._uris.discard(uri)
        for identifier in self._identifiers:
            self._d.pop((uri, identifier), None)

    def __iter__(self) -> Iterator[DocumentUri]:
        return iter(self._uris)

    def __len__(self) -> int:
        return len(self._uris)

    def register(self, identifier: str) -> None:
        """ Register an identifier for a diagnostics stream. """
        self._identifiers.add(identifier)

    def unregister(self, identifier: str) -> None:
        """ Unregister an identifier for a diagnostics stream. """
        self._identifiers.discard(identifier)

    def filter_map_diagnostics_async(
        self, pred: Callable[[Diagnostic], bool], f: Callable[[DocumentUri, Diagnostic], T]
    ) -> Iterator[tuple[DocumentUri, list[T]]]:
        """
        Yields `(uri, results)` items with `results` being a list of `f(diagnostic)` for each
        diagnostic for this `uri` with `pred(diagnostic) == True`, filtered by `bool(f(diagnostic))`.
        Only `uri`s with non-empty `results` are returned. Each `uri` is guaranteed to be yielded
        not more than once.
        """
        for uri, diagnostics in self.items():
            results: list[T] = list(filter(None, map(functools.partial(f, uri), filter(pred, diagnostics))))
            if results:
                yield uri, results

    def filter_map_diagnostics_flat_async(self, pred: Callable[[Diagnostic], bool],
                                          f: Callable[[DocumentUri, Diagnostic], T]) -> Iterator[tuple[DocumentUri, T]]:
        """
        Flattened variant of `filter_map_diagnostics_async()`. Yields `(uri, result)` items for each
        of the `result`s per `uri` instead. Each `uri` can be yielded more than once. Items are
        grouped by `uri` and each `uri` group is guaranteed to appear not more than once.
        """
        for uri, results in self.filter_map_diagnostics_async(pred, f):
            for result in results:
                yield uri, result

    def sum_total_errors_and_warnings_async(self) -> tuple[int, int]:
        """
        Returns `(total_errors, total_warnings)` count of all diagnostics currently in store.
        """
        return (
            sum(map(severity_count(DiagnosticSeverity.Error), self.values())),
            sum(map(severity_count(DiagnosticSeverity.Warning), self.values())),
        )


def severity_count(severity: int) -> Callable[[list[Diagnostic]], int]:
    def severity_count(diagnostics: list[Diagnostic]) -> int:
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
