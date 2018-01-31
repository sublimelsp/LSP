import sublime

from sublime_plugin import TextCommand

from .logging import debug, exception_log
from .configurations import config_for_scope, is_supported_view
from .protocol import Notification, Request
from .workspace import get_project_path

# typing only
from .rpc import Client
from .settings import ClientConfig
assert Client and ClientConfig


try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass


clients_by_window = {}  # type: Dict[int, Dict[str, Client]]


class LspTextCommand(TextCommand):
    # Passing capability='' due Sublime Text bug: https://github.com/SublimeTextIssues/Core/issues/2175
    def __init__(self, view, capability='', last_check=lambda: True):
        super(LspTextCommand, self).__init__(view)
        self.capability = capability
        self.last_check = last_check

    def is_visible(self):
        return is_supported_view(self.view)

    def is_enabled(self):
        client = client_for_view(self.view)
        if client and client.has_capability(self.capability):
            return self.last_check()
        return False


def window_clients(window: sublime.Window) -> 'Dict[str, Client]':
    if window.id() in clients_by_window:
        return clients_by_window[window.id()]
    else:
        # debug("no clients found for window", window.id())
        return {}


def add_window_client(window: sublime.Window, config_name: str, client: 'Client'):
    global clients_by_window
    clients_by_window.setdefault(window.id(), {})[config_name] = client
    debug("{} client registered for window {}".format(config_name, window.id()))


def remove_window_client(window: sublime.Window, config_name: str):
    del clients_by_window[window.id()][config_name]


def client_for_view(view: sublime.View) -> 'Optional[Client]':
    window = view.window()
    if not window:
        debug("no window for view", view.file_name())
        return None

    config = config_for_scope(view)
    if not config:
        debug("config not available for view", view.file_name())
        return None

    clients = window_clients(window)
    if config.name not in clients:
        debug(config.name, "not available for view",
              view.file_name(), "in window", window.id())
        return None
    else:
        return clients[config.name]


def unload_all_clients():
    for window in sublime.windows():
        for client in window_clients(window).values():
            unload_client(client)


def check_window_unloaded():
    global clients_by_window
    open_window_ids = list(window.id() for window in sublime.windows())
    iterable_clients_by_window = clients_by_window.copy()
    closed_windows = []
    for id, window_clients in iterable_clients_by_window.items():
        if id not in open_window_ids:
            debug("window closed", id)
            closed_windows.append(id)
    for closed_window_id in closed_windows:
        unload_window_clients(closed_window_id)


def unload_window_clients(window_id: int):
    global clients_by_window
    if window_id in clients_by_window:
        window_clients = clients_by_window[window_id]
        del clients_by_window[window_id]
        for config, client in window_clients.items():
            debug("unloading client", config, client)
            unload_client(client)


def unload_old_clients(window: sublime.Window):
    project_path = get_project_path(window)
    clients_by_config = window_clients(window)
    clients_to_unload = {}
    for config_name, client in clients_by_config.items():
        if client and client.get_project_path() != project_path:
            debug('unload', config_name, 'project path changed from', client.get_project_path(), 'to', project_path)
            clients_to_unload[config_name] = client

    for config_name, client in clients_to_unload.items():
        del clients_by_config[config_name]
        unload_client(client)


def on_shutdown(client: Client, response):
    try:
        client.send_notification(Notification.exit())
    except Exception as err:
        exception_log("Error exiting server", err)


def unload_client(client: Client):
    client.send_request(Request.shutdown(), lambda response: on_shutdown(client, response))
