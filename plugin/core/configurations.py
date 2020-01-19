from copy import deepcopy
from .types import ClientConfig, LanguageConfig, ViewLike, WindowLike, ConfigRegistry, base_scope_from_view
from .types import base_scope_from_syntax
from .logging import debug
from .workspace import get_project_config, enable_in_project, disable_in_project
from .typing import Any, List, Dict, Tuple, Optional, Iterator, Iterable
import sublime


def get_scope_client_config(view: sublime.View, configs: List[ClientConfig],
                            point: Optional[int] = None) -> Optional[ClientConfig]:
    return next(get_scope_client_configs(view, configs, point), None)


def get_scope_client_configs(view: sublime.View, configs: List[ClientConfig],
                             point: Optional[int] = None) -> Iterator[ClientConfig]:
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


def get_global_client_config(view: 'sublime.View', global_configs: List[ClientConfig]) -> Optional[ClientConfig]:
    return get_scope_client_config(view, global_configs)


def create_window_configs(window: WindowLike, global_configs: List[ClientConfig]) -> List[ClientConfig]:
    window_config = get_project_config(window)
    return list(map(lambda c: apply_project_overrides(c, window_config), global_configs))


def apply_project_overrides(client_config: ClientConfig, lsp_project_settings: dict) -> ClientConfig:
    if client_config.name in lsp_project_settings:
        overrides = lsp_project_settings[client_config.name]
        debug('window has override for {}'.format(client_config.name), overrides)
        client_settings = _merge_dicts(client_config.settings, overrides.get("settings", {}))
        client_env = _merge_dicts(client_config.env, overrides.get("env", {}))
        return ClientConfig(
            name=client_config.name,
            binary_args=overrides.get("command", client_config.binary_args),
            tcp_port=overrides.get("tcp_port", client_config.tcp_port),
            scopes=[],
            languageId="",
            languages=client_config.languages,
            enabled=overrides.get("enabled", client_config.enabled),
            init_options=overrides.get("initializationOptions", client_config.init_options),
            settings=client_settings,
            env=client_env,
            tcp_host=overrides.get("tcp_host", client_config.tcp_host),
        )

    return client_config


def syntax_language(config: ClientConfig, scope: str) -> Optional[LanguageConfig]:
    for language in config.languages:
        for lang_scope in language.scopes:
            if lang_scope == scope:
                return language
    return None


def config_supports_syntax(config: ClientConfig, syntax: str) -> bool:
    base_scope = base_scope_from_syntax(syntax)
    return config.supports(base_scope)


def is_supported_syntax(syntax: str, configs: List[ClientConfig]) -> bool:
    base_scope = base_scope_from_syntax(syntax)
    return any(config.supports(base_scope) for config in configs)


class ConfigManager(object):
    """Distributes language client configuration between windows"""

    def __init__(self, global_configs: List[ClientConfig]) -> None:
        self._configs = global_configs
        self._managers = {}  # type: Dict[int, ConfigRegistry]

    def for_window(self, window: WindowLike) -> ConfigRegistry:
        window_configs = WindowConfigManager(window, self._configs)
        self._managers[window.id()] = window_configs
        return window_configs

    def update(self) -> None:
        for window in sublime.windows():
            if window.id() in self._managers:
                self._managers[window.id()].update()


class WindowConfigManager(object):
    def __init__(self, window: WindowLike, global_configs: List[ClientConfig]) -> None:
        self._window = window
        self._global_configs = global_configs
        self._temp_disabled_configs = []  # type: List[str]
        self.all = create_window_configs(window, global_configs)

    def is_supported(self, view: Any) -> bool:
        base_scope = base_scope_from_view(view)
        return any(config.supports(base_scope) for config in self.all)

    def scope_configs(self, view: Any, point: Optional[int] = None) -> Iterator[ClientConfig]:
        return get_scope_client_configs(view, self.all, point)

    def syntax_configs(self, view: Any, include_disabled: bool = False) -> Iterable[ClientConfig]:
        scope = base_scope_from_view(view)
        for config in self.all:
            if (include_disabled or config.enabled) and config.supports(scope):
                yield config

    def syntax_supported(self, view: ViewLike) -> bool:
        scope = base_scope_from_view(view)
        for config in self.all:
            if config.enabled and config.supports(scope):
                return True
        return False

    def syntax_config_languages(self, view: ViewLike) -> Dict[str, LanguageConfig]:
        scope = base_scope_from_view(view)
        config_languages = {}
        for config in self.all:
            if config.enabled:
                language = syntax_language(config, scope)
                if language:
                    config_languages[config.name] = language
        return config_languages

    def update(self) -> None:
        self.all = create_window_configs(self._window, self._global_configs)
        for config in self.all:
            if config.name in self._temp_disabled_configs:
                config.enabled = False

    def enable_config(self, config_name: str) -> None:
        enable_in_project(self._window, config_name)
        self.update()

    def disable_config(self, config_name: str) -> None:
        disable_in_project(self._window, config_name)
        self.update()

    def disable_temporarily(self, config_name: str) -> None:
        self._temp_disabled_configs.append(config_name)
        self.update()


def _merge_dicts(dict_a: dict, dict_b: dict) -> dict:
    """Merge dict_b into dict_a with one level of recurse"""
    result_dict = deepcopy(dict_a)
    for key, value in dict_b.items():
        if isinstance(result_dict.get(key), dict) and isinstance(value, dict):
            result_dict.setdefault(key, {}).update(value)
        else:
            result_dict[key] = value
    return result_dict
