import sublime
import os
import tempfile
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


def get_window_env(window: sublime.Window, config: ClientConfig) -> 'Tuple[List[str], Dict[str, str]]':

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


def get_expanding_variables(window: sublime.Window) -> dict:
    variables = window.extract_variables()
    variables.update({
        "home": os.path.expanduser('~'),
        "temp_dir": tempfile.gettempdir(),
    })

    return variables


def expand_variables_for_dict(window: sublime.Window,
                              d: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in d.items():
        if isinstance(value, dict):
            d[key] = expand_variables_for_dict(window, value)
        elif isinstance(value, str):
            d[key] = sublime.expand_variables(value, get_expanding_variables(window))

    return d


def start_window_config(window: sublime.Window,
                        project_path: str,
                        config: ClientConfig,
                        on_pre_initialize: 'Callable[[Session], None]',
                        on_post_initialize: 'Callable[[Session], None]',
                        on_post_exit: 'Callable[[str], None]') -> 'Optional[Session]':
    args, env = get_window_env(window, config)
    config.binary_args = args
    config.init_options = expand_variables_for_dict(window, config.init_options)
    return create_session(config=config,
                          project_path=project_path,
                          env=env,
                          settings=settings,
                          on_pre_initialize=on_pre_initialize,
                          on_post_initialize=on_post_initialize,
                          on_post_exit=lambda config_name: on_session_ended(window, config_name, on_post_exit))


def on_session_ended(window: sublime.Window, config_name: str, on_post_exit_handler: 'Callable[[str], None]') -> None:
    on_post_exit_handler(config_name)
