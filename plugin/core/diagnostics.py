from .logging import debug
from .url import uri_to_filename
from .protocol import Diagnostic
assert Diagnostic

try:
    import sublime
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert sublime
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass


class DiagnosticsUpdate(object):
    def __init__(self, window, client_name: str,
                 file_path: str, diagnostics: 'List[Diagnostic]') -> 'None':
        self.window = window
        self.client_name = client_name
        self.file_path = file_path
        self.diagnostics = diagnostics


class WindowDiagnostics(object):

    def __init__(self):
        self._diagnostics = {}  # type: Dict[str, Dict[str, List[Diagnostic]]]
        self._on_updated = None  # type: Optional[Callable]

    def get(self) -> 'Dict[str, Dict[str, List[Diagnostic]]]':
        return self._diagnostics

    def set_on_updated(self, update_handler: 'Callable'):
        self._on_updated = update_handler

    def get_by_path(self, file_path: str) -> 'List[Diagnostic]':
        view_diagnostics = []
        if file_path in self._diagnostics:
            for origin in self._diagnostics[file_path]:
                view_diagnostics.extend(self._diagnostics[file_path][origin])
        return view_diagnostics

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

    def clear(self):
        for file_path in self._diagnostics:
            for client_name in self._diagnostics[file_path]:
                self.update(file_path, client_name, [])
                self._on_updated(file_path, client_name, [])

    def handle_client_diagnostics(self, client_name: str, update: dict):
        maybe_file_uri = update.get('uri')
        if maybe_file_uri is not None:
            file_path = uri_to_filename(maybe_file_uri)

            diagnostics = list(
                Diagnostic.from_lsp(item) for item in update.get('diagnostics', []))

            if self.update(file_path, client_name, diagnostics):
                if self._on_updated:
                    self._on_updated(file_path, client_name, diagnostics)
        else:
            debug('missing uri in diagnostics update')

    def remove(self, file_path: str, client_name: str):
        self.update(file_path, client_name, [])
