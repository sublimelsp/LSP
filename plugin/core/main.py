
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
from .events import Events
from .registry import windows, load_handlers, unload_sessions


def startup():
    load_settings()
    set_debug_logging(settings.log_debug)
    load_handlers()
    Events.subscribe("view.on_load_async", on_view_activated)
    Events.subscribe("view.on_activated_async", on_view_activated)
    if settings.show_status_messages:
        sublime.status_message("LSP initialized")
    start_active_window()


def shutdown():
    unload_settings()
    unload_sessions()


def start_active_window():
    window = sublime.active_window()
    if window:
        windows.lookup(window).start_active_views()


def on_view_activated(view: sublime.View):
    window = view.window()
    if window:
        windows.lookup(window).activate_view(view)
