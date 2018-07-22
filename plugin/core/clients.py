import sublime
import sublime_plugin
import os

from .logging import debug
from .configurations import config_for_scope, is_supported_view
from .workspace import get_project_path
from .types import ClientStates
from .sessions import create_session, Session

# typing only
from .rpc import Client
from .settings import ClientConfig, settings
assert Client and ClientConfig


try:
    from typing import Any, List, Dict, Tuple, Callable, Optional, Set
    assert Any and List and Dict and Tuple and Callable and Optional and Set
    assert Session
except ImportError:
    pass


clients_by_window = {}  # type: Dict[int, Dict[str, Session]]


class LspTextCommand(sublime_plugin.TextCommand):
    def __init__(self, view):
        super().__init__(view)

    def is_visible(self, event=None):
        return is_supported_view(self.view)

    def has_client_with_capability(self, capability):
        session = session_for_view(self.view)
        if session and session.has_capability(capability):
            return True
        return False


def window_configs(window: sublime.Window) -> 'Dict[str, Session]':
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


def get_window_env(window: sublime.Window, config: ClientConfig):

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

    return expanded_args, env


def start_window_config(window: sublime.Window, project_path: str, config: ClientConfig,
                        on_created: 'Callable', on_ended: 'Callable'):
    args, env = get_window_env(window, config)
    config.binary_args = args
    session = create_session(config, project_path, env, settings,
                             on_created=on_created,
                             on_ended=lambda: on_session_ended(window, config.name, on_ended))
    clients_by_window.setdefault(window.id(), {})[config.name] = session
    debug("{} client registered for window {}".format(config.name, window.id()))
    return session


def on_session_ended(window: sublime.Window, config_name: str, on_ended_handler: 'Callable'):
    on_ended_handler(config_name)
    # todo: this needs to be cleaned up from window-specific logic
    configs = window_configs(window)
    del configs[config_name]


def set_config_stopping(window: sublime.Window, config_name: str):
    window_configs(window)[config_name].state = ClientStates.STOPPING


def client_for_closed_view(view: sublime.View) -> 'Optional[Client]':
    return _client_for_view_and_window(view, sublime.active_window())


def client_for_view(view: sublime.View) -> 'Optional[Client]':
    return _client_for_view_and_window(view, view.window())


def session_for_view(view: sublime.View) -> 'Optional[Session]':
    return _session_for_view_and_window(view, view.window())


def _session_for_view_and_window(view: sublime.View, window: 'Optional[sublime.Window]') -> 'Optional[Session]':
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
        session = window_config_states[config.name]
        if session.state == ClientStates.READY:
            return session
        else:
            return None


def _client_for_view_and_window(view: sublime.View, window: 'Optional[sublime.Window]') -> 'Optional[Client]':
    session = _session_for_view_and_window(view, window)

    if session:
        if session.client:
            return session.client
        else:
            debug(session.config.name, "in state", session.state, " for view",
                  view.file_name())
            return None
    else:
        debug('no session found')
        return None


# Shutdown

def remove_window_client(window: sublime.Window, config_name: str):
    del clients_by_window[window.id()][config_name]


def unload_all_clients():
    for window in sublime.windows():
        for config_name, session in window_configs(window).items():
            if session.client:
                if session.state == ClientStates.STARTING:
                    session.end()
                else:
                    debug('ignoring unload of session in state', session.state)
            else:
                debug('ignoring session of config without client')


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
        unload_window_sessions(closed_window_id)
    closing_window_ids.clear()


def unload_window_sessions(window_id: int):
    if window_id in clients_by_window:
        window_configs = clients_by_window[window_id]
        for config_name, session in window_configs.items():
            window_configs[config_name].state = ClientStates.STOPPING
            debug("unloading session", config_name)
            session.end()


def unload_old_clients(window: sublime.Window):
    project_path = get_project_path(window)
    configs = window_configs(window)
    for config_name, session in configs.items():
        if session.client and session.state == ClientStates.READY and session.project_path != project_path:
            debug('unload', config_name, 'project path changed from',
                  session.project_path, 'to', project_path)
            session.end()
