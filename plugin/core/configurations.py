from .collections import DottedDict
from .logging import debug
from .types import ClientConfig, view2scope
from .typing import Any, Generator, List, Dict, Set
from .workspace import enable_in_project, disable_in_project
from copy import deepcopy
import sublime


class ConfigManager(object):
    """Distributes language client configuration between windows"""

    def __init__(self, global_configs: List[ClientConfig]) -> None:
        self._configs = global_configs
        self._managers = {}  # type: Dict[int, WindowConfigManager]

    def for_window(self, window: sublime.Window) -> 'WindowConfigManager':
        window_configs = WindowConfigManager(window, self._configs)
        self._managers[window.id()] = window_configs
        return window_configs

    def update(self) -> None:
        for window in sublime.windows():
            if window.id() in self._managers:
                self._managers[window.id()].update()


class WindowConfigManager(object):
    def __init__(self, window: sublime.Window, global_configs: List[ClientConfig]) -> None:
        self._window = window
        self._global_configs = global_configs
        self._temp_disabled_configs = set()  # type: Set[str]
        self.all = self._create_window_configs()

    def get_configs(self) -> List[ClientConfig]:
        return sorted(self.all, key=lambda config: config.name)

    def match_scope(self, scope: str) -> Generator[ClientConfig, None, None]:
        """
        Yields configurations which match one of their document selectors to the given scope.
        """
        for config in self.all:
            if config.match_scope(scope):
                yield config

    def match_view(self, view: sublime.View, include_disabled: bool = False) -> Generator[ClientConfig, None, None]:
        """
        Yields configurations matching with the language's document_selector
        """
        try:
            configs = self.match_scope(view2scope(view))
            if include_disabled:
                yield from configs
            else:
                for config in configs:
                    if config.enabled:
                        yield config
        except IndexError:
            # We're in the worker thread, and the view is already closed. This means view.scope_name(0) returns an
            # empty string.
            pass

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
        self._temp_disabled_configs.add(config_name)
        self.update()

    def _create_window_configs(self) -> List[ClientConfig]:
        project_clients_dict = (self._window.project_data() or {}).get("settings", {}).get("LSP", {})
        return [self._apply_project_overrides(c, project_clients_dict) for c in self._global_configs]

    def _apply_project_overrides(self, client_config: ClientConfig, project_clients: Dict[str, Any]) -> ClientConfig:
        overrides = project_clients.get(client_config.name)
        if overrides:
            debug('applying .sublime-project override for', client_config.name)
            settings = DottedDict(deepcopy(client_config.settings.get()))
            settings.update(overrides.get("settings", {}))
            env = deepcopy(client_config.env)
            for key, value in overrides.get("env", {}).items():
                env[key] = value
            return ClientConfig(
                name=client_config.name,
                binary_args=overrides.get("command", client_config.binary_args),
                languages=client_config.languages,
                tcp_port=overrides.get("tcp_port", client_config.tcp_port),
                enabled=overrides.get("enabled", client_config.enabled),
                init_options=overrides.get("initializationOptions", client_config.init_options),
                settings=settings,
                env=env,
                tcp_host=overrides.get("tcp_host", client_config.tcp_host),
                experimental_capabilities=overrides.get(
                    "experimental_capabilities", client_config.experimental_capabilities),
            )

        return client_config
