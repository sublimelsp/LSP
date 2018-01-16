import sublime

from .logging import debug
from .url import uri_to_filename
from .protocol import Diagnostic
from .events import Events

assert Diagnostic

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass


window_file_diagnostics = dict(
)  # type: Dict[int, Dict[str, Dict[str, List[Diagnostic]]]]


def update_file_diagnostics(window: sublime.Window, file_path: str, source: str,
                            diagnostics: 'List[Diagnostic]'):
    if diagnostics:
        window_file_diagnostics.setdefault(window.id(), dict()).setdefault(
            file_path, dict())[source] = diagnostics
    else:
        if window.id() in window_file_diagnostics:
            file_diagnostics = window_file_diagnostics[window.id()]
            if file_path in file_diagnostics:
                if source in file_diagnostics[file_path]:
                    del file_diagnostics[file_path][source]
                if not file_diagnostics[file_path]:
                    del file_diagnostics[file_path]


class DiagnosticsUpdate(object):

    def __init__(self, file_path: str, diagnostics: 'List[Diagnostic]') -> 'None':
        self.file_path = file_path
        self.diagnostics = diagnostics


def handle_diagnostics(update: 'Any'):
    file_path = uri_to_filename(update.get('uri'))
    window = sublime.active_window()

    diagnostics = list(
        Diagnostic.from_lsp(item) for item in update.get('diagnostics', []))

    origin = 'lsp'  # TODO: use actual client name to be able to update diagnostics per client
    update_file_diagnostics(window, file_path, origin, diagnostics)
    Events.publish("document.diagnostics", DiagnosticsUpdate(file_path, diagnostics))
    # TODO: expose updates to features


def remove_diagnostics(view: sublime.View):
    """Removes diagnostics for a file if no views exist for it
    """
    window = sublime.active_window()

    file_path = view.file_name()
    if file_path:
        if not window.find_open_file(file_path):
            update_file_diagnostics(window, file_path, 'lsp', [])
            Events.publish("document.diagnostics", DiagnosticsUpdate(file_path, []))
        else:
            debug('file still open?')


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
        if diagnostic.range.to_region(view).contains(point)
    )


def get_window_diagnostics(window: sublime.Window) -> 'Optional[Dict[str, Dict[str, List[Diagnostic]]]]':
    return window_file_diagnostics.get(window.id())


def get_diagnostics_for_view(view: sublime.View) -> 'List[Diagnostic]':
    window = view.window()
    file_path = view.file_name()
    origin = 'lsp'
    if file_path and window:
        if window.id() in window_file_diagnostics:
            file_diagnostics = window_file_diagnostics[window.id()]
            if file_path in file_diagnostics:
                if origin in file_diagnostics[file_path]:
                    return file_diagnostics[file_path][origin]
    return []
