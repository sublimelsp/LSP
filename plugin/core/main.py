import sublime

from .settings import settings, load_settings, unload_settings
from .logging import set_debug_logging, set_server_logging
from .registry import windows, load_handlers, unload_sessions
from .panels import destroy_output_panels
from .popups import popups
from ..diagnostics import DiagnosticsPresenter
from ..highlights import remove_highlights
from ..color import remove_color_boxes

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional, Set
    assert Any and List and Dict and Tuple and Callable and Optional and Set
except ImportError:
    pass


def startup() -> None:
    load_settings()
    set_debug_logging(settings.log_debug)
    set_server_logging(settings.log_server)
    popups.load_css()
    windows.set_diagnostics_ui(DiagnosticsPresenter)
    load_handlers()
    sublime.status_message("LSP initialized")
    start_active_window()


def shutdown() -> None:
    # Also needs to handle package being disabled or removed
    # https://github.com/tomv564/LSP/issues/375
    unload_settings()

    for window in sublime.windows():
        unload_sessions(window)  # unloads view state from document sync and diagnostics
        destroy_output_panels(window)  # references and diagnostics panels

        for view in window.views():
            if view.file_name():
                remove_highlights(view)
                remove_color_boxes(view)


def start_active_window() -> None:
    window = sublime.active_window()
    if window:
        windows.lookup(window).start_active_views()
