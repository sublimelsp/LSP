import sublime
from copy import deepcopy
from .logging import debug
from .types import ClientConfig, LanguageConfig, WindowLike, syntax2scope, view2scope
from .typing import Any, List, Dict, Optional, Iterator, Iterable
from .workspace import get_project_config, enable_in_project, disable_in_project


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
            client_config.name,
            overrides.get("command", client_config.binary_args),
            overrides.get("tcp_port", client_config.tcp_port),
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


def is_supported_syntax(syntax: str, configs: Iterable[ClientConfig]) -> bool:
    scope = syntax2scope(syntax)
    if scope is not None:
        for config in configs:
            if config.supports(scope):
                return True
    return False


class ConfigManager(object):
    """Distributes language client configuration between windows"""

    def __init__(self, global_configs: List[ClientConfig]) -> None:
        self._configs = global_configs
        self._managers = {}  # type: Dict[int, WindowConfigManager]

    def for_window(self, window: WindowLike) -> 'WindowConfigManager':
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
        return any(self.scope_configs(view))

    def scope_configs(self, view: Any, point: Optional[int] = None) -> Iterator[ClientConfig]:
        scope = view2scope(view, point)
        for config in self.all:
            if config.supports(scope):
                yield config

    def syntax_configs(self, view: Any, include_disabled: bool = False) -> List[ClientConfig]:
        scope = view2scope(view)
        return list(filter(lambda c: c.supports(scope) and (c.enabled or include_disabled), self.all))

    def syntax_supported(self, view: sublime.View) -> bool:
        scope = view2scope(view)
        for found in filter(lambda c: c.supports(scope) and c.enabled, self.all):
            return True
        return False

    def syntax_config_languages(self, view: sublime.View) -> Dict[str, LanguageConfig]:
        scope = view2scope(view)
        config_languages = {}
        for config in self.all:
            if config.enabled:
                for language in config.languages:
                    if language.score(scope) > 0:
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
