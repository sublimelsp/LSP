import sublime
import os
import tempfile
from .sessions import create_session, Session

# typing only
from .rpc import Client
from .settings import ClientConfig, settings
assert Client and ClientConfig


try:
    from typing import Any, List, Dict, Tuple, Callable, Optional, Set, TypeVar
    assert Any and List and Dict and Tuple and Callable and Optional and Set and TypeVar
    assert Session

    T = TypeVar('T')
except ImportError:
    pass


def get_window_env(window: sublime.Window, config: ClientConfig) -> 'Tuple[List[str], Dict[str, str]]':

    # Create a dictionary of Sublime Text variables
    variables = get_expanding_variables(window)

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


def get_expanding_variables(window: sublime.Window) -> dict:
    variables = window.extract_variables()
    variables.update({
        "home": os.path.expanduser('~'),
        "temp_dir": tempfile.gettempdir(),
    })

    return variables


def lsp_expand_variables(window: sublime.Window, var: 'T') -> 'T':
    if isinstance(var, dict):
        for key, value in var.items():
            if isinstance(value, (dict, list, str)):
                var[key] = lsp_expand_variables(window, value)
    elif isinstance(var, list):
        for idx, value in enumerate(var):
            if isinstance(value, (dict, list, str)):
                var[idx] = lsp_expand_variables(window, value)
    elif isinstance(var, str):
        var = sublime.expand_variables(var, get_expanding_variables(window))

    return var


def start_window_config(window: sublime.Window,
                        project_path: str,
                        config: ClientConfig,
                        on_pre_initialize: 'Callable[[Session], None]',
                        on_post_initialize: 'Callable[[Session], None]',
                        on_post_exit: 'Callable[[str], None]') -> 'Optional[Session]':
    args, env = get_window_env(window, config)
    config.binary_args = args
    config.init_options = lsp_expand_variables(window, config.init_options)
    return create_session(config=config,
                          project_path=project_path,
                          env=env,
                          settings=settings,
                          on_pre_initialize=on_pre_initialize,
                          on_post_initialize=on_post_initialize,
                          on_post_exit=lambda config_name: on_session_ended(window, config_name, on_post_exit))


def on_session_ended(window: sublime.Window, config_name: str, on_post_exit_handler: 'Callable[[str], None]') -> None:
    on_post_exit_handler(config_name)
