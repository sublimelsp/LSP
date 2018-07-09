
try:
    from typing import Any, List, Dict, Tuple, Callable, Optional, Set
    assert Any and List and Dict and Tuple and Callable and Optional and Set
except ImportError:
    pass

import sublime_plugin
import sublime

from .settings import (
    ClientConfig, settings, load_settings, unload_settings
)
from .handlers import LanguageHandler
from .logging import debug, set_debug_logging
from .configurations import (
    is_supported_view, register_client_config, ConfigManager
)
from .clients import (
    start_window_config,
    unload_window_sessions, unload_all_clients, register_clients_unloaded_handler
)
from .events import Events
from .documents import (
    clear_document_states, GlobalDocumentHandler
)
from .diagnostics import GlobalDiagnostics
from .windows import WindowRegistry


configs = ConfigManager()
diagnostics = GlobalDiagnostics()
documents = GlobalDocumentHandler()
windows = WindowRegistry(configs, documents, diagnostics, start_window_config)


def startup():
    load_settings()
    set_debug_logging(settings.log_debug)
    load_handlers()
    Events.subscribe("view.on_load_async", on_view_activated)
    Events.subscribe("view.on_activated_async", on_view_activated)
    register_clients_unloaded_handler(handle_clients_unloaded)
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

# open_after_initialize_by_window = dict()  # type: Dict[int, List[sublime.View]]
unsubscribe_initialize_on_load = None
unsubscribe_initialize_on_activated = None


client_start_listeners = {}  # type: Dict[str, Callable]
client_initialization_listeners = {}  # type: Dict[str, Callable]


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


def handle_server_crash(window: sublime.Window, config: ClientConfig):
    msg = "Language server {} has crashed, do you want to restart it?".format(config.name)
    result = sublime.ok_cancel_dialog(msg, ok_title="Restart")
    if result == sublime.DIALOG_YES:
        restart_window_clients(window)


restarting_window_ids = set()  # type: Set[int]


def restart_window_clients(window: sublime.Window):
    clear_document_states(window)
    restarting_window_ids.add(window.id())
    unload_window_sessions(window.id())


def handle_clients_unloaded(window_id):
    debug('clients for window {} unloaded'.format(window_id))
    if window_id in restarting_window_ids:
        restarting_window_ids.remove(window_id)
        start_active_window()


def handle_message_request(params: dict):
    message = params.get("message", "(missing message)")
    actions = params.get("actions", [])
    addendum = "TODO: showMessageRequest with actions:"
    titles = list(action.get("title") for action in actions)
    sublime.message_dialog("\n".join([message, addendum] + titles))


class LspRestartClientCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        return is_supported_view(self.view)

    def run(self, edit):
        window = self.view.window()
        restart_window_clients(window)


class LspStartClientCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        return is_supported_view(self.view)

    def run(self, edit):
        start_active_window()
