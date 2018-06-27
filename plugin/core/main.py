import os

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional, Set
    assert Any and List and Dict and Tuple and Callable and Optional and Set
except ImportError:
    pass

import sublime_plugin
import sublime

from .protocol import Notification
from .settings import (
    ClientConfig, settings, load_settings, unload_settings
)
from .handlers import LanguageHandler
from .logging import debug, server_log, set_debug_logging
from .rpc import attach_tcp_client, attach_stdio_client
from .workspace import get_project_path
from .configurations import (
    config_for_scope, is_supported_view, register_client_config
)
from .clients import (
    start_window_config,
    can_start_config,
    window_configs, is_ready_window_config,
    unload_old_clients, unload_window_sessions, unload_all_clients, register_clients_unloaded_handler
)
from .events import Events
from .documents import (
    initialize_document_sync, notify_did_open, clear_document_states
)
from .diagnostics import handle_client_diagnostics, remove_diagnostics
from .edit import apply_workspace_edit
from .process import start_server


def startup():
    load_settings()
    set_debug_logging(settings.log_debug)
    load_handlers()
    Events.subscribe("view.on_load_async", initialize_on_open)
    Events.subscribe("view.on_activated_async", initialize_on_open)
    register_clients_unloaded_handler(handle_clients_unloaded)
    if settings.show_status_messages:
        sublime.status_message("LSP initialized")
    start_active_views()


def shutdown():
    unload_settings()
    unload_all_clients()


def start_active_views():
    window = sublime.active_window()
    if window:
        views = list()  # type: List[sublime.View]
        num_groups = window.num_groups()
        for group in range(0, num_groups):
            view = window.active_view_in_group(group)
            if is_supported_view(view):
                if window.active_group() == group:
                    views.insert(0, view)
                else:
                    views.append(view)

        if len(views) > 0:
            first_view = views.pop(0)
            debug('starting active=', first_view.file_name(), 'other=', len(views))
            initialize_on_open(first_view)
            if len(views) > 0:
                for view in views:
                    open_after_initialize_by_window[window.id()].append(view)


TextDocumentSyncKindNone = 0
TextDocumentSyncKindFull = 1
TextDocumentSyncKindIncremental = 2

open_after_initialize_by_window = dict()  # type: Dict[int, List[sublime.View]]
unsubscribe_initialize_on_load = None
unsubscribe_initialize_on_activated = None


def initialize_on_open(view: sublime.View):
    window = view.window()

    if not window:
        return

    debug("initialize on open", window.id(), view.file_name())

    if window_configs(window):
        unload_old_clients(window)

    global didopen_after_initialize
    open_after_initialize_by_window[window.id()] = []
    config = config_for_scope(view)
    if config:
        if config.enabled:
            if not is_ready_window_config(window, config.name):
                open_after_initialize_by_window[window.id()].append(view)
                start_window_client(view, window, config)
        else:
            debug(config.name, 'is not enabled')


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


def handle_session_started(session, window, project_path, config):
    client = session.client
    client.set_crash_handler(lambda: handle_server_crash(window, config))
    client.set_error_display_handler(lambda msg: sublime.status_message(msg))

    # handle server requests and notifications
    client.on_request(
        "workspace/applyEdit",
        lambda params: apply_workspace_edit(window, params))

    client.on_request(
        "window/showMessageRequest",
        lambda params: handle_message_request(params))

    client.on_notification(
        "textDocument/publishDiagnostics",
        lambda params: handle_client_diagnostics(window, config.name, params))

    client.on_notification(
        "window/showMessage",
        lambda params: sublime.message_dialog(params.get("message")))

    if settings.log_server:
        client.on_notification(
            "window/logMessage",
            lambda params: server_log(params.get("message")))

    if config.name in client_initialization_listeners:
        client_initialization_listeners[config.name](client)

    # TODO: These handlers is already filtered by syntax but does not need to
    # be enabled 2x per client
    # Move filtering?
    document_sync = session.capabilities.get("textDocumentSync")
    if document_sync:
        initialize_document_sync(document_sync)

    Events.subscribe('view.on_close', lambda view: remove_diagnostics(view, config.name))

    client.send_notification(Notification.initialized())
    if config.settings:
        configParams = {
            'settings': config.settings
        }
        client.send_notification(Notification.didChangeConfiguration(configParams))

    for view in open_after_initialize_by_window[window.id()]:
        notify_did_open(view)

    if settings.show_status_messages:
        window.status_message("{} initialized".format(config.name))
    del open_after_initialize_by_window[window.id()]


def start_client(window: sublime.Window, project_path: str, config: ClientConfig):

    if config.name in client_start_listeners:
        handler_startup_hook = client_start_listeners[config.name]
        if not handler_startup_hook(window):
            return

    if settings.show_status_messages:
        window.status_message("Starting " + config.name + "...")
    debug("starting in", project_path)

    # Create a dictionary of Sublime Text variables
    variables = window.extract_variables()

    # Expand language server command line environment variables
    expanded_args = list(
        sublime.expand_variables(os.path.expanduser(arg), variables)
        for arg in config.binary_args
    )

    # Override OS environment variables
    env = os.environ.copy()
    for var, value in config.env.items():
        # Expand both ST and OS environment variables
        env[var] = os.path.expandvars(sublime.expand_variables(value, variables))

    # TODO: don't start process if tcp already up or command empty?
    process = start_server(expanded_args, project_path, env)
    if not process:
        window.status_message("Could not start " + config.name + ", disabling")
        debug("Could not start", config.binary_args, ", disabling")
        return None

    if config.tcp_port is not None:
        client = attach_tcp_client(config.tcp_port, process, settings)
    else:
        client = attach_stdio_client(process, settings)

    if not client:
        window.status_message("Could not connect to " + config.name + ", disabling")
        return None

    return client


def start_window_client(view: sublime.View, window: sublime.Window, config: ClientConfig):
    project_path = get_project_path(window)
    if project_path is None:
        debug('Cannot start without a project folder')
        return

    if can_start_config(window, config.name):
        if config.name in client_start_listeners:
            handler_startup_hook = client_start_listeners[config.name]
            if not handler_startup_hook(window):
                return

        if settings.show_status_messages:
            window.status_message("Starting " + config.name + "...")
        debug("starting in", project_path)
        start_window_config(window, project_path, config,
                            lambda session: handle_session_started(session, window, project_path, config))
    else:
        debug('Already starting on this window:', config.name)


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
        start_active_views()


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
        start_active_views()
