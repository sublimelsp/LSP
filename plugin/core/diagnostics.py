import sublime

from .logging import debug
from .url import uri_to_filename
from .protocol import Diagnostic
from .events import global_events
from .views import range_to_region
from .windows import WindowLike, ViewLike

assert Diagnostic

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
    assert ViewLike and WindowLike
except ImportError:
    pass


global_diagnostics = dict(
)  # type: Dict[int, Dict[str, Dict[str, List[Diagnostic]]]]


def update_file_diagnostics(window: sublime.Window, file_path: str, source: str,
                            diagnostics: 'List[Diagnostic]') -> bool:
    updated = False
    if diagnostics:
        file_diagnostics = global_diagnostics.setdefault(window.id(), dict()).setdefault(
            file_path, dict())
        file_diagnostics[source] = diagnostics
        updated = True
    else:
        if window.id() in global_diagnostics:
            window_diagnostics = global_diagnostics[window.id()]
            if file_path in window_diagnostics:
                if source in window_diagnostics[file_path]:
                    updated = True
                    del window_diagnostics[file_path][source]
                if not window_diagnostics[file_path]:
                    del window_diagnostics[file_path]
    return updated


class DiagnosticsUpdate(object):
    def __init__(self, window: sublime.Window, client_name: str,
                 file_path: str, diagnostics: 'List[Diagnostic]') -> 'None':
        self.window = window
        self.client_name = client_name
        self.file_path = file_path
        self.diagnostics = diagnostics


def handle_client_diagnostics(window: sublime.Window, client_name: str, update: dict):
    maybe_file_uri = update.get('uri')
    if maybe_file_uri is not None:
        file_path = uri_to_filename(maybe_file_uri)

        diagnostics = list(
            Diagnostic.from_lsp(item) for item in update.get('diagnostics', []))

        if update_file_diagnostics(window, file_path, client_name, diagnostics):
            global_events.publish("document.diagnostics",
                                  DiagnosticsUpdate(window, client_name, file_path, diagnostics))
    else:
        debug('missing uri in diagnostics update')
# TODO: expose updates to features


def remove_diagnostics(view: sublime.View, client_name: str):
    """Removes diagnostics for a file
    """
    window = view.window() or sublime.active_window()

    file_path = view.file_name()
    if file_path:
        if update_file_diagnostics(window, file_path, client_name, []):
            global_events.publish("document.diagnostics", DiagnosticsUpdate(window, client_name, file_path, []))


class GlobalDiagnostics(object):
    def update(self, window: 'Any', client_name: str, update: dict):
        handle_client_diagnostics(window, client_name, update)

    def remove(self, view: 'Any', client_name: str):
        """Removes diagnostics for a file if no views exist for it
        """
        remove_diagnostics(view, client_name)


def get_line_diagnostics(view, point):
    row, _ = view.rowcol(point)
    diagnostics = get_diagnostics_for_view(view)
    return tuple(
        diagnostic for diagnostic in diagnostics
        if diagnostic.range.start.row <= row <= diagnostic.range.end.row
    )


def get_point_diagnostics(view, point):
    diagnostics = get_diagnostics_for_view(view)
    return tuple(
        diagnostic for diagnostic in diagnostics
        if range_to_region(diagnostic.range, view).contains(point)
    )


def get_window_diagnostics(window: sublime.Window) -> 'Optional[Dict[str, Dict[str, List[Diagnostic]]]]':
    return global_diagnostics.get(window.id())


def get_diagnostics_for_view(view: sublime.View) -> 'List[Diagnostic]':
    view_diagnostics = []
    window = view.window()
    file_path = view.file_name()
    if file_path and window:
        if window.id() in global_diagnostics:
            file_diagnostics = global_diagnostics[window.id()]
            if file_path in file_diagnostics:
                for origin in file_diagnostics[file_path]:
                    view_diagnostics.extend(file_diagnostics[file_path][origin])
    return view_diagnostics
