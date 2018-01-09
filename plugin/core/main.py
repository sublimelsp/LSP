import os
import subprocess

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional, Set
    assert Any and List and Dict and Tuple and Callable and Optional and Set
except ImportError:
    pass

import sublime_plugin
import sublime

from .url import filename_to_uri
from .protocol import (
    Request, Notification
)
from .settings import (
    ClientConfig, settings, load_settings, unload_settings
)
from .logging import debug, exception_log, server_log
from .rpc import Client
from .workspace import get_project_path
from .configurations import (
    config_for_scope, is_supported_view
)
from .clients import (
    add_window_client, window_clients, unload_old_clients,
    unload_window_clients, unload_all_clients
)
from .events import Events
from .documents import (
    initialize_document_sync, notify_did_open, clear_document_states
)
from .diagnostics import handle_diagnostics, remove_diagnostics
from .edit import apply_workspace_edit


def startup():
    load_settings()
    Events.subscribe("view.on_load_async", initialize_on_open)
    Events.subscribe("view.on_activated_async", initialize_on_open)
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
                    didopen_after_initialize.append(view)


TextDocumentSyncKindNone = 0
TextDocumentSyncKindFull = 1
TextDocumentSyncKindIncremental = 2

didopen_after_initialize = list()
unsubscribe_initialize_on_load = None
unsubscribe_initialize_on_activated = None


starting_configs_by_window = {}  # type: Dict[int, Set[str]]


def is_starting_config(window: sublime.Window, config_name: str):
    if window.id() in starting_configs_by_window:
        return config_name in starting_configs_by_window[window.id()]
    else:
        return False


def set_starting_config(window: sublime.Window, config_name: str):
    starting_configs_by_window.setdefault(window.id(), set()).add(config_name)


def clear_starting_config(window: sublime.Window, config_name: str):
    starting_configs_by_window[window.id()].remove(config_name)


def initialize_on_open(view: sublime.View):
    window = view.window()

    if not window:
        return

    if window_clients(window):
        unload_old_clients(window)

    global didopen_after_initialize
    config = config_for_scope(view)
    if config:
        if config.enabled:
            if config.name not in window_clients(window):
                didopen_after_initialize.append(view)
                start_window_client(view, window, config)
        else:
            debug(config.name, 'is not enabled')


client_initialization_listeners = {}  # type: Dict[str, Callable]


def register_client_initialization_listener(client_name: str, handler: 'Callable') -> None:
    debug('received client callback for', client_name)
    client_initialization_listeners[client_name] = handler


def handle_initialize_result(result, client, window, config):
    global didopen_after_initialize
    capabilities = result.get("capabilities")
    client.set_capabilities(capabilities)

    # handle server requests and notifications
    client.on_request(
        "workspace/applyEdit",
        lambda params: apply_workspace_edit(sublime.active_window(), params))

    client.on_notification(
        "textDocument/publishDiagnostics",
        lambda params: handle_diagnostics(params))
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
    document_sync = capabilities.get("textDocumentSync")
    if document_sync:
        initialize_document_sync(document_sync)

    Events.subscribe('view.on_close', remove_diagnostics)

    client.send_notification(Notification.initialized())
    if config.settings:
        configParams = {
            'settings': config.settings
        }
        client.send_notification(Notification.didChangeConfiguration(configParams))

    # now the client should be available outside the initialization sequence
    add_window_client(window, config.name, client)
    clear_starting_config(window, config.name)

    for view in didopen_after_initialize:
        notify_did_open(view)

    if settings.show_status_messages:
        window.status_message("{} initialized".format(config.name))
    didopen_after_initialize = list()


def start_client(window: sublime.Window, config: ClientConfig):
    project_path = get_project_path(window)
    if project_path is None:
        return None

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

    client = start_server(expanded_args, project_path, env)
    if not client:
        window.status_message("Could not start " + config.name + ", disabling")
        debug("Could not start", config.binary_args, ", disabling")
        return None

    client.set_crash_handler(lambda: handle_server_crash(window, config))

    initializeParams = {
        "processId": client.process.pid,
        "rootUri": filename_to_uri(project_path),
        "rootPath": project_path,
        "capabilities": {
            "textDocument": {
                "completion": {
                    "completionItem": {
                        "snippetSupport": True
                    }
                },
                "synchronization": {
                    "didSave": True
                }
            },
            "workspace": {
                "applyEdit": True
            }
        }
    }
    if config.init_options:
        initializeParams['initializationOptions'] = config.init_options

    client.send_request(
        Request.initialize(initializeParams),
        lambda result: handle_initialize_result(result, client, window, config))
    return client


def start_window_client(view: sublime.View, window: sublime.Window, config: ClientConfig):
    if not is_starting_config(window, config.name):
        set_starting_config(window, config.name)
        client = start_client(window, config)
        if client is None:  # clear starting state for config if not starting.
            clear_starting_config(window, config.name)
    else:
        debug('Already starting on this window:', config.name)


def start_server(server_binary_args, working_dir, env):
    debug("starting " + str(server_binary_args))
    si = None
    if os.name == "nt":
        si = subprocess.STARTUPINFO()  # type: ignore
        si.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW  # type: ignore
    try:
        process = subprocess.Popen(
            server_binary_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=working_dir,
            env=env,
            startupinfo=si)
        return Client(process, working_dir)

    except Exception as err:
        sublime.status_message("Failed to start LSP server {}".format(str(server_binary_args)))
        exception_log("Failed to start server", err)


def handle_server_crash(window: sublime.Window, config: ClientConfig):
    msg = "Language server {} has crashed, do you want to restart it?".format(config.name)
    result = sublime.ok_cancel_dialog(msg, ok_title="Restart")
    if result == sublime.DIALOG_YES:
        restart_window_clients(window)


def restart_window_clients(window: sublime.Window):
    clear_document_states(window)
    unload_window_clients(window.id())
    start_active_views()


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
