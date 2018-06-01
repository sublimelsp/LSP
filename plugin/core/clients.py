import sublime
import sublime_plugin

from .logging import debug, exception_log
from .configurations import config_for_scope, is_supported_view
from .workspace import get_project_path

# typing only
from .rpc import Client
from .settings import ClientConfig
assert Client and ClientConfig


try:
    from typing import Any, List, Dict, Tuple, Callable, Optional, Set
    assert Any and List and Dict and Tuple and Callable and Optional and Set
except ImportError:
    pass


clients_by_window = {}  # type: Dict[int, Dict[str, ConfigState]]


class ClientStates(object):
    STARTING = 0
    READY = 1
    STOPPING = 2


class ConfigState(object):

    def __init__(self, state=ClientStates.STARTING, client=None):
        self.state = state
        self.client = client


class LspTextCommand(sublime_plugin.TextCommand):
    def __init__(self, view):
        super().__init__(view)

    def is_visible(self, event=None):
        return is_supported_view(self.view)

    def has_client_with_capability(self, capability):
        client = client_for_view(self.view)
        if client and client.has_capability(capability):
            return True
        return False


def window_configs(window: sublime.Window) -> 'Dict[str, ConfigState]':
    if window.id() in clients_by_window:
        return clients_by_window[window.id()]
    else:
        # debug("no configs found for window", window.id())
        return {}


def is_ready_window_config(window: sublime.Window, config_name: str):
    configs = window_configs(window)

    if config_name not in configs:
        return False

    if configs[config_name].state == ClientStates.READY:
        return True

    return False


# Startup

def can_start_config(window: sublime.Window, config_name: str):
    return config_name not in window_configs(window)


def set_config_starting(window: sublime.Window, config_name: str):
    clients_by_window.setdefault(window.id(), {})[config_name] = ConfigState()


def clear_config_state(window: sublime.Window, config_name: str):
    configs = window_configs(window)
    del configs[config_name]


def set_config_ready(window: sublime.Window, config_name: str, client: 'Client'):
    window_configs(window)[config_name] = ConfigState(ClientStates.READY, client)
    debug("{} client registered for window {}".format(config_name, window.id()))


def set_config_stopping(window: sublime.Window, config_name: str):
    window_configs(window)[config_name].state = ClientStates.STOPPING


def client_for_closed_view(view: sublime.View) -> 'Optional[Client]':
    return _client_for_view_and_window(view, sublime.active_window())


def client_for_view(view: sublime.View) -> 'Optional[Client]':
    return _client_for_view_and_window(view, view.window())


def _client_for_view_and_window(view: sublime.View, window: 'Optional[sublime.Window]') -> 'Optional[Client]':
    if not window:
        debug("no window for view", view.file_name())
        return None

    config = config_for_scope(view)
    if not config:
        debug("config not available for view", view.file_name())
        return None

    window_config_states = window_configs(window)
    if config.name not in window_config_states:
        debug(config.name, "not available for view",
              view.file_name(), "in window", window.id())
        return None
    else:
        config_state = window_config_states[config.name]
        if config_state.client:
            return config_state.client
        else:
            debug(config.name, "in state", config_state.state, " for view",
                  view.file_name(), "in window", window.id())
            return None


# Shutdown

def remove_window_client(window: sublime.Window, config_name: str):
    del clients_by_window[window.id()][config_name]


def unload_all_clients():
    for window in sublime.windows():
        for config_name, config_state in window_configs(window).items():
            if config_state.client:
                if config_state.state == ClientStates.STARTING:
                    unload_client(config_state.client, window.id(), config_name)
                else:
                    debug('ignoring unload of config in state', config_state.state)
            else:
                debug('ignoring unload of config without client')


closing_window_ids = set()  # type: Set[int]


def check_window_unloaded():
    global clients_by_window
    open_window_ids = list(window.id() for window in sublime.windows())
    iterable_clients_by_window = clients_by_window.copy()
    for id, window_clients in iterable_clients_by_window.items():
        if id not in open_window_ids and window_clients:
            if id not in closing_window_ids:
                closing_window_ids.add(id)
                debug("window closed", id)
    for closed_window_id in closing_window_ids:
        unload_window_clients(closed_window_id)
    closing_window_ids.clear()


def unload_window_clients(window_id: int):
    if window_id in clients_by_window:
        window_configs = clients_by_window[window_id]
        for config_name, state in window_configs.items():
            window_configs[config_name].state = ClientStates.STOPPING
            debug("unloading client", config_name, state.client)
            unload_client(state.client, window_id, config_name)


def unload_old_clients(window: sublime.Window):
    project_path = get_project_path(window)
    configs = window_configs(window)
    clients_to_unload = {}
    for config_name, state in configs.items():
        if state.client and state.state == ClientStates.READY and state.client.get_project_path() != project_path:
            debug('unload', config_name, 'project path changed from',
                  state.client.get_project_path(), 'to', project_path)
            clients_to_unload[config_name] = state.client

    for config_name, client in clients_to_unload.items():
        set_config_stopping(window, config_name)
        unload_client(client, window.id(), config_name)


clients_unloaded_handler = None  # type: Optional[Callable]


def register_clients_unloaded_handler(handler: 'Callable'):
    global clients_unloaded_handler
    clients_unloaded_handler = handler


def on_shutdown(client: Client, window_id: int, config_name: str, response):
    try:
        client.exit()
        del clients_by_window[window_id][config_name]

        if not clients_by_window[window_id]:
            debug("all clients unloaded")
            if clients_unloaded_handler:
                clients_unloaded_handler(window_id)

    except Exception as err:
        exception_log("Error exiting server", err)


def unload_client(client: Client, window_id: int, config_name: str):
    client.send_request(
        client.request_class.shutdown(),
        lambda response: on_shutdown(client, window_id, config_name, response))
