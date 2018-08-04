
try:
    from typing import Any, List, Dict, Tuple, Callable, Optional, Set
    assert Any and List and Dict and Tuple and Callable and Optional and Set
except ImportError:
    pass

import sublime

from .settings import (
    settings, load_settings, unload_settings
)
from .logging import set_debug_logging
from .events import global_events
from .registry import windows, load_handlers, unload_sessions
from .panels import destroy_output_panels


def startup():
    load_settings()
    set_debug_logging(settings.log_debug)
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
    unload_sessions()  # unloads view state from document sync and diagnostics
    unload_panels()  # references and diagnostics panels


def unload_panels():
    for window in sublime.windows():
        destroy_output_panels(window)


def start_active_window():
    window = sublime.active_window()
    if window:
        windows.lookup(window).start_active_views()


def on_view_activated(view: sublime.View):
    window = view.window()
    if window:
        windows.lookup(window).activate_view(view)
