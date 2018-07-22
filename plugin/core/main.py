
try:
    from typing import Any, List, Dict, Tuple, Callable, Optional, Set
    assert Any and List and Dict and Tuple and Callable and Optional and Set
except ImportError:
    pass

import sublime_plugin
import sublime

from .settings import (
    settings, load_settings, unload_settings
)
from .handlers import LanguageHandler
from .logging import debug, set_debug_logging
from .configurations import (
    is_supported_view, register_client_config, ConfigManager
)
from .clients import (
    start_window_config, unload_all_clients
)
from .events import Events
from .documents import (
    GlobalDocumentHandler
)
from .diagnostics import GlobalDiagnostics
from .windows import WindowRegistry


class SublimeUI(object):
    DIALOG_CANCEL = sublime.DIALOG_CANCEL
    DIALOG_YES = sublime.DIALOG_YES
    DIALOG_NO = sublime.DIALOG_NO

    def message_dialog(self, msg: str) -> None:
        sublime.message_dialog(msg)

    def ok_cancel_dialog(self, msg: str, ok_title: str) -> bool:
        return sublime.ok_cancel_dialog(msg, ok_title)

    def yes_no_cancel_dialog(self, msg, yes_title: str, no_title: str) -> int:
        return sublime.yes_no_cancel_dialog(msg, yes_title, no_title)


client_start_listeners = {}  # type: Dict[str, Callable]
client_initialization_listeners = {}  # type: Dict[str, Callable]


class LanguageHandlerDispatcher(object):

    def on_start(self, config_name: str) -> bool:
        if config_name in client_start_listeners:
            return client_start_listeners[config_name]()
        else:
            return True

    def on_initialized(self, config_name: str, client):
        if config_name in client_initialization_listeners:
            client_initialization_listeners[config_name](client)


configs = ConfigManager()
diagnostics = GlobalDiagnostics()
documents = GlobalDocumentHandler()
handlers_dispatcher = LanguageHandlerDispatcher()
windows = WindowRegistry(configs, documents, diagnostics, start_window_config, SublimeUI(), handlers_dispatcher)


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
    unload_all_clients()


def start_active_window():
    window = sublime.active_window()
    if window:
        windows.lookup(window).start_active_views()


def on_view_activated(view: sublime.View):
    window = view.window()
    if window:
        windows.lookup(window).activate_view(view)


TextDocumentSyncKindNone = 0
TextDocumentSyncKindFull = 1
TextDocumentSyncKindIncremental = 2

unsubscribe_initialize_on_load = None
unsubscribe_initialize_on_activated = None


def load_handlers():
    for handler in LanguageHandler.instantiate_all():
        register_language_handler(handler)


def register_language_handler(handler: LanguageHandler) -> None:
    debug("received config {} from {}".format(handler.name, handler.__class__.__name__))
    register_client_config(handler.config)
    if handler.on_start:
        client_start_listeners[handler.name] = handler.on_start
    if handler.on_initialized:
        client_initialization_listeners[handler.name] = handler.on_initialized


class LspRestartClientCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        return is_supported_view(self.view)

    def run(self, edit):
        window = self.view.window()
        if window:
            windows.lookup(window).restart_sessions()


class LspStartClientCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        return is_supported_view(self.view)

    def run(self, edit):
        start_active_window()
