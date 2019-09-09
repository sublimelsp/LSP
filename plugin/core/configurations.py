import re
from copy import deepcopy

from .types import ClientConfig, LanguageConfig
from .logging import debug
from .types import config_supports_syntax
from .workspace import get_project_config
from .windows import ViewLike, WindowLike, ConfigRegistry

assert ClientConfig

try:
    import sublime
    from typing import Any, List, Dict, Tuple, Callable, Optional, Iterator
    assert sublime
    assert Any and List and Dict and Tuple and Callable and Optional and Iterator
    assert ViewLike and WindowLike and ConfigRegistry and LanguageConfig
except ImportError:
    pass


def get_scope_client_config(view: 'sublime.View', configs: 'List[ClientConfig]',
                            point: 'Optional[int]' = None) -> 'Optional[ClientConfig]':
    return next(get_scope_client_configs(view, configs, point), None)


def get_scope_client_configs(view: 'sublime.View', configs: 'List[ClientConfig]',
                             point: 'Optional[int]' = None) -> 'Iterator[ClientConfig]':
    # When there are multiple server configurations, all of which are for
    # similar scopes (e.g. 'source.json', 'source.json.sublime.settings') the
    # configuration with the most specific scope (highest ranked selector)
    # in the current position is preferred.
    if point is None:
        sel = view.sel()
        if len(sel) > 0:
            point = sel[0].begin()

    languages = view.settings().get('lsp_language', None)
    scope_configs = []  # type: List[Tuple[ClientConfig, Optional[int]]]

    for config in configs:
        if config.enabled:
            if languages is None or config.name in languages:
                for language in config.languages:
                    for scope in language.scopes:
                        score = 0
                        if point is not None:
                            score = view.score_selector(point, scope)
                        if score > 0:
                            scope_configs.append((config, score))
                            # debug('scope {} score {}'.format(scope, score))

    return (config_score[0] for config_score in sorted(
        scope_configs, key=lambda config_score: config_score[1], reverse=True))


def get_global_client_config(view: 'sublime.View', global_configs: 'List[ClientConfig]') -> 'Optional[ClientConfig]':
    return get_scope_client_config(view, global_configs)


def create_window_configs(window: 'sublime.Window', global_configs: 'List[ClientConfig]') -> 'List[ClientConfig]':
    return list(map(lambda c: apply_window_settings(c, window), global_configs))


def apply_window_settings(client_config: 'ClientConfig', window: 'sublime.Window') -> 'ClientConfig':
    window_config = get_project_config(window)

    if client_config.name in window_config:
        overrides = window_config[client_config.name]
        debug('window {} has override for {}'.format(window.id(), client_config.name), overrides)
        client_settings = _merge_dicts(client_config.settings, overrides.get("settings", {}))
        client_env = _merge_dicts(client_config.env, overrides.get("env", {}))
        return ClientConfig(
            client_config.name,
            overrides.get("command", client_config.binary_args),
            overrides.get("tcp_port", client_config.tcp_port),
            [],
            [],
            "",
            client_config.languages,
            overrides.get("enabled", client_config.enabled),
            overrides.get("initializationOptions", client_config.init_options),
            client_settings,
            client_env,
            overrides.get("tcp_host", client_config.tcp_host),
        )

    return client_config


def is_supported_syntax(syntax: str, configs: 'List[ClientConfig]') -> bool:
    for config in configs:
        for language in config.languages:
            if re.search(r'|'.join(r'\b%s\b' % re.escape(s) for s in language.syntaxes), syntax, re.IGNORECASE):
                return True
    return False


def syntax_language(config: 'ClientConfig', syntax: str) -> 'Optional[LanguageConfig]':
    for language in config.languages:
        if re.search(r'|'.join(r'\b%s\b' % re.escape(s) for s in language.syntaxes), syntax, re.IGNORECASE):
            return language
    return None


class ConfigManager(object):
    """Distributes language client configuration between windows"""

    def __init__(self, global_configs: 'List[ClientConfig]') -> None:
        self._configs = global_configs
        self._managers = {}  # type: Dict[int, ConfigRegistry]

    def for_window(self, window: 'Any') -> 'ConfigRegistry':
        window_configs = WindowConfigManager(create_window_configs(window, self._configs))
        self._managers[window.id()] = window_configs
        return window_configs

    def update(self) -> None:
        for window in sublime.windows():
            if window.id() in self._managers:
                self._managers[window.id()].update(create_window_configs(window, self._configs))


class WindowConfigManager(object):
    def __init__(self, configs: 'List[ClientConfig]') -> None:
        self.all = configs

    def is_supported(self, view: 'Any') -> bool:
        return any(self.scope_configs(view))

    def scope_configs(self, view: 'Any', point=None) -> 'Iterator[ClientConfig]':
        return get_scope_client_configs(view, self.all, point)

    def syntax_configs(self, view: 'Any') -> 'List[ClientConfig]':
        syntax = view.settings().get("syntax")
        return list(filter(lambda c: config_supports_syntax(c, syntax) and c.enabled, self.all))

    def syntax_supported(self, view: ViewLike) -> bool:
        syntax = view.settings().get("syntax")
        for found in filter(lambda c: config_supports_syntax(c, syntax) and c.enabled, self.all):
            return True
        return False

    def syntax_config_languages(self, view: ViewLike) -> 'Dict[str, LanguageConfig]':
        syntax = view.settings().get("syntax")
        config_languages = {}
        for config in self.all:
            if config.enabled:
                language = syntax_language(config, syntax)
                if language:
                    config_languages[config.name] = language
        return config_languages

    def update(self, configs: 'List[ClientConfig]') -> None:
        self.all = configs

    def disable(self, config_name: str) -> None:
        for config in self.all:
            if config.name == config_name:
                config.enabled = False


def _merge_dicts(dict_a: dict, dict_b: dict) -> dict:
    """Merge dict_b into dict_a with one level of recurse"""
    result_dict = deepcopy(dict_a)
    for key, value in dict_b.items():
        if isinstance(result_dict.get(key), dict) and isinstance(value, dict):
            result_dict.setdefault(key, {}).update(value)
        else:
            result_dict[key] = value
    return result_dict
