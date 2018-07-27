import re
import sublime

from .settings import ClientConfig, client_configs
from .logging import debug
from .workspace import get_project_config
from .windows import ViewLike

assert ClientConfig

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
    assert ViewLike
except ImportError:
    pass


def get_scope_client_config(view: 'sublime.View', configs: 'List[ClientConfig]') -> 'Optional[ClientConfig]':
    # When there are multiple server configurations, all of which are for
    # similar scopes (e.g. 'source.json', 'source.json.sublime.settings') the
    # configuration with the most specific scope (highest ranked selector)
    # in the current position is preferred.
    scope_score = 0
    scope_client_config = None
    for config in configs:
        for scope in config.scopes:
            sel = view.sel()
            if len(sel) > 0:
                score = view.score_selector(sel[0].begin(), scope)
                if score > scope_score:
                    scope_score = score
                    scope_client_config = config
    return scope_client_config


def register_client_config(config: ClientConfig) -> None:
    # todo: how to propagate global config changes to all window-specific configs.
    # window_client_configs.clear()
    client_configs.add_external_config(config)


def get_global_client_config(view: sublime.View) -> 'Optional[ClientConfig]':
    return get_scope_client_config(view, client_configs.all)


def get_default_client_config(view: sublime.View) -> 'Optional[ClientConfig]':
    return get_scope_client_config(view, client_configs.defaults)


def create_window_configs(window: 'sublime.Window') -> 'List[ClientConfig]':
    return list(map(lambda c: apply_window_settings(c, window), client_configs.all))


def apply_window_settings(client_config: 'ClientConfig', window: 'sublime.Window') -> 'ClientConfig':
    window_config = get_project_config(window)

    if client_config.name in window_config:
        overrides = window_config[client_config.name]
        debug('window has override for', client_config.name, overrides)
        return ClientConfig(
            client_config.name,
            overrides.get("command", client_config.binary_args),
            overrides.get("tcp_port", client_config.tcp_port),
            overrides.get("scopes", client_config.scopes),
            overrides.get("syntaxes", client_config.syntaxes),
            overrides.get("languageId", client_config.languageId),
            overrides.get("enabled", client_config.enabled),
            overrides.get("initializationOptions", client_config.init_options),
            overrides.get("settings", client_config.settings),
            overrides.get("env", client_config.env)
        )

    return client_config


def is_supportable_syntax(syntax: str) -> bool:
    # TODO: filter out configs disabled by the user.
    for config in client_configs.defaults:
        if re.search(r'|'.join(r'\b%s\b' % re.escape(s) for s in config.syntaxes), syntax, re.IGNORECASE):
            return True
    return False


def is_supported_syntax(syntax: str) -> bool:
    for config in client_configs.all:
        if re.search(r'|'.join(r'\b%s\b' % re.escape(s) for s in config.syntaxes), syntax, re.IGNORECASE):
            return True
    return False


class ConfigManager(object):

    def for_window(self, window: 'Any') -> 'WindowConfigManager':
        return WindowConfigManager(create_window_configs(window))


class WindowConfigManager(object):
    def __init__(self, configs: 'List[ClientConfig]') -> None:
        self._configs = configs

    def is_supported(self, view: 'Any') -> bool:
        return self.scope_config(view) is not None

    def scope_config(self, view: 'Any') -> 'Optional[ClientConfig]':
        return get_scope_client_config(view, self._configs)
