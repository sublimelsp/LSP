import re
import sublime

from .settings import ClientConfig, client_configs, LanguageConfig
from .logging import debug
from .workspace import get_project_config
from .windows import ViewLike, WindowLike, ConfigRegistry

assert ClientConfig

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
    assert ViewLike and WindowLike and ConfigRegistry and LanguageConfig
except ImportError:
    pass


def get_scope_client_config(view: 'sublime.View', configs: 'List[ClientConfig]',
                            point: 'Optional[int]'=None) -> 'Optional[ClientConfig]':
    # When there are multiple server configurations, all of which are for
    # similar scopes (e.g. 'source.json', 'source.json.sublime.settings') the
    # configuration with the most specific scope (highest ranked selector)
    # in the current position is preferred.
    scope_score = 0
    scope_client_config = None
    if point is None:
        sel = view.sel()
        if len(sel) > 0:
            point = sel[0].begin()

    for config in configs:
        if config.enabled:
            for language in config.languages:
                for scope in language.scopes:
                    if point is not None:
                        score = view.score_selector(point, scope)
                        # if score > 0:
                        #     debug('scope match score', scope, config.name, score)
                        if score > scope_score:
                            scope_score = score
                            scope_client_config = config
    # debug('chose ', scope_client_config.name if scope_client_config else None)
    return scope_client_config


def get_global_client_config(view: sublime.View) -> 'Optional[ClientConfig]':
    return get_scope_client_config(view, client_configs.all)


def create_window_configs(window: 'sublime.Window') -> 'List[ClientConfig]':
    return list(map(lambda c: apply_window_settings(c, window), client_configs.all))


def apply_window_settings(client_config: 'ClientConfig', window: 'sublime.Window') -> 'ClientConfig':
    window_config = get_project_config(window)

    if client_config.name in window_config:
        overrides = window_config[client_config.name]
        debug('window {} has override for {}'.format(window.id(), client_config.name), overrides)
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
            overrides.get("settings", client_config.settings),
            overrides.get("env", client_config.env),
            overrides.get("tcp_host", client_config.tcp_host)
        )

    return client_config


def is_supported_syntax(syntax: str) -> bool:
    for config in client_configs.all:
        for language in config.languages:
            if re.search(r'|'.join(r'\b%s\b' % re.escape(s) for s in language.syntaxes), syntax, re.IGNORECASE):
                return True
    return False


def config_supports_syntax(config: 'ClientConfig', syntax: str) -> bool:
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

    def for_window(self, window: 'Any') -> 'ConfigRegistry':
        return WindowConfigManager(create_window_configs(window))


class WindowConfigManager(object):
    def __init__(self, configs: 'List[ClientConfig]') -> None:
        self.all = configs

    def is_supported(self, view: 'Any') -> bool:
        return self.scope_config(view) is not None

    def scope_config(self, view: 'Any', point=None) -> 'Optional[ClientConfig]':
        return get_scope_client_config(view, self.all, point)

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
