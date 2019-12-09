import sublime

from .logging import set_debug_logging
from .logging import set_exception_logging
from .settings import settings, load_settings, unload_settings
from .registry import windows, load_handlers, unload_sessions
from .panels import destroy_output_panels
from .panels import ensure_panel
from .popups import popups
from ..diagnostics import DiagnosticsPresenter
from ..highlights import remove_highlights
from ..color import remove_color_boxes

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional, Set
    assert Any and List and Dict and Tuple and Callable and Optional and Set
except ImportError:
    pass


def ensure_server_panel(window: sublime.Window) -> 'Optional[sublime.View]':
    return ensure_panel(window, "language servers", "", "", "Packages/LSP/Syntaxes/ServerLog.sublime-syntax")


def startup() -> None:
    load_settings()
    popups.load_css()
    set_debug_logging(settings.log_debug)
    set_exception_logging(True)
    windows.set_diagnostics_ui(DiagnosticsPresenter)
    windows.set_server_panel_factory(ensure_server_panel)
    windows.set_settings_factory(settings)
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
