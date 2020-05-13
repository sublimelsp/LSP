import sublime
from copy import deepcopy
from .logging import debug
from .types import ClientConfig, WindowLike, syntax2scope, view2scope
from .typing import Any, Generator, List, Dict, Iterable
from .workspace import enable_in_project, disable_in_project


def is_supported_syntax(syntax: str, configs: Iterable[ClientConfig]) -> bool:
    scope = syntax2scope(syntax)
    if scope is not None:
        return any(config.match_document(scope) for config in configs)
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
        self.all = self._create_window_configs()

    def match_document(self, scope: str) -> Generator[ClientConfig, None, None]:
        """
        Yields configurations which match one of their document selectors to the given scope.
        """
        for config in self.all:
            if config.match_document(scope):
                yield config

    def match_view(self, view: sublime.View, include_disabled: bool = False) -> Generator[ClientConfig, None, None]:
        """
        Yields configurations matching with the language's document_selector
        """
        configs = self.match_document(view2scope(view))
        if include_disabled:
            yield from configs
        else:
            for config in configs:
                if config.enabled:
                    yield config

    def is_supported(self, view: Any) -> bool:
        return any(self.match_view(view))

    def update(self) -> None:
        self.all = self._create_window_configs()
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

    def _create_window_configs(self) -> List[ClientConfig]:
        project_clients_dict = (self._window.project_data() or {}).get("settings", {}).get("LSP", {})
        return [self._apply_project_overrides(c, project_clients_dict) for c in self._global_configs]

    def _apply_project_overrides(self, client_config: ClientConfig, project_clients: Dict[str, Any]) -> ClientConfig:
        overrides = project_clients.get(client_config.name)
        if overrides:
            debug('window has override for {}'.format(client_config.name), overrides)
            client_settings = _merge_dicts(client_config.settings, overrides.get("settings", {}))
            client_env = _merge_dicts(client_config.env, overrides.get("env", {}))
            return ClientConfig(
                name=client_config.name,
                binary_args=overrides.get("command", client_config.binary_args),
                languages=client_config.languages,
                tcp_port=overrides.get("tcp_port", client_config.tcp_port),
                enabled=overrides.get("enabled", client_config.enabled),
                init_options=overrides.get("initializationOptions", client_config.init_options),
                settings=client_settings,
                env=client_env,
                tcp_host=overrides.get("tcp_host", client_config.tcp_host),
                experimental_capabilities=overrides.get(
                    "experimental_capabilities", client_config.experimental_capabilities),
            )

        return client_config


def _merge_dicts(dict_a: dict, dict_b: dict) -> dict:
    """Merge dict_b into dict_a with one level of recurse"""
    result_dict = deepcopy(dict_a)
    for key, value in dict_b.items():
        if isinstance(result_dict.get(key), dict) and isinstance(value, dict):
            result_dict.setdefault(key, {}).update(value)
        else:
            result_dict[key] = value
    return result_dict
