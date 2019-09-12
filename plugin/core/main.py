from ..highlights import remove_highlights
from ..color import remove_color_boxes

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional, Set
    assert Any and List and Dict and Tuple and Callable and Optional and Set
except ImportError:
    pass

import sublime

from .settings import (
    settings, load_settings, unload_settings
)
from .logging import set_debug_logging, set_server_logging
from .events import global_events
from .registry import windows, load_handlers, unload_sessions
from .panels import destroy_output_panels


def startup():
    load_settings()
    set_debug_logging(settings.log_debug)
    set_server_logging(settings.log_server)
    load_handlers()
    global_events.subscribe("view.on_load_async", on_view_activated)
    global_events.subscribe("view.on_activated_async", on_view_activated)
    if settings.show_status_messages:
        sublime.status_message("LSP initialized")
    start_active_window()


def shutdown():
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


def start_active_window():
    window = sublime.active_window()
    if window:
        windows.lookup(window).start_active_views()


def on_view_activated(view: sublime.View):
    window = view.window()
    if window:
        windows.lookup(window).activate_view(view)
