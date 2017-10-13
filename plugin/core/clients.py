import sublime

from .logging import debug
from .configurations import config_for_scope
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


def window_clients(window: sublime.Window) -> 'Dict[str, Client]':
    if window.id() in clients_by_window:
        return clients_by_window[window.id()]
    else:
        # debug("no clients found for window", window.id())
        return {}


def add_window_client(window: sublime.Window, config_name: str, client: 'Client'):
    clients_by_window.setdefault(window.id(), {})[config_name] = client
    debug("{} client registered for window {}".format(config_name, window.id()))


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
    for clients_by_config in clients_by_window.values():
        for client in clients_by_config.values():
            client.shutdown()
    clients_by_window.clear()


def check_window_unloaded():
    open_window_ids = set(window.id() for window in sublime.windows())
    closed_windows = set(id for id in clients_by_window if id not in open_window_ids)
    for closed_window_id in closed_windows:
        debug("window closed", closed_window_id)
        unload_window_clients(closed_window_id)


def unload_window_clients(window_id: int):
    clients_by_config = clients_by_window.pop(window_id)
    if clients_by_config:
        for client in clients_by_config.values():
            client.shutdown()
        clients_by_config.clear()


def unload_old_clients(window: sublime.Window):
    project_path = get_project_path(window)
    clients_by_config = window_clients(window)
    clients_to_unload = []
    for config_name, client in clients_by_config.items():
        if client and client.get_project_path() != project_path:
            debug('unload', config_name, 'project path changed from ', client.get_project_path())
            clients_to_unload.append(config_name)

    for config_name in clients_to_unload:
        clients_by_config.pop(config_name).shutdown()
