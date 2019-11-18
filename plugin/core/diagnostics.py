from .logging import debug
from .url import uri_to_filename
from .protocol import Diagnostic
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
