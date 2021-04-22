from .logging import debug
from .types import ClientConfig
from .typing import Any, Generator, List, Set, Dict
from .workspace import enable_in_project, disable_in_project
import sublime


class ConfigManager(object):
    """Distributes language client configuration between windows"""

    def __init__(self, global_configs: Dict[str, ClientConfig]) -> None:
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
    def __init__(self, window: sublime.Window, global_configs: Dict[str, ClientConfig]) -> None:
        self._window = window
        self._global_configs = global_configs
        self._disabled_for_session = set()  # type: Set[str]
        self.all = {}  # type: Dict[str, ClientConfig]
        self.update()

    def get_configs(self) -> List[ClientConfig]:
        return sorted(self.all.values(), key=lambda config: config.name)

    def match_view(self, view: sublime.View, include_disabled: bool = False) -> Generator[ClientConfig, None, None]:
        """
        Yields configurations matching with the language's document_selector
        """
        try:
            for config in self.all.values():
                if config.match_view(view):
                    if config.enabled:
                        yield config
                    elif include_disabled:
                        yield config
        except IndexError:
            # We're in the worker thread, and the view is already closed. This means view.scope_name(0) returns an
            # empty string.
            pass

    def is_supported(self, view: Any) -> bool:
        return any(self.match_view(view))

    def update(self) -> None:
        project_settings = (self._window.project_data() or {}).get("settings", {}).get("LSP", {})
        self.all.clear()
        for name, config in self._global_configs.items():
            overrides = project_settings.pop(name, None)
            if isinstance(overrides, dict):
                debug("applying .sublime-project override for", name)
            else:
                overrides = {}
            if name in self._disabled_for_session:
                overrides["enabled"] = False
            self.all[name] = ClientConfig.from_config(config, overrides)
        for name, c in project_settings.items():
            debug("loading project-only configuration", name)
            self.all[name] = ClientConfig.from_dict(name, c)
        self._window.run_command("lsp_recheck_sessions")

    def enable_config(self, config_name: str) -> None:
        if not self._reenable_disabled_for_session(config_name):
            enable_in_project(self._window, config_name)
        self.update()

    def disable_config(self, config_name: str, only_for_session: bool = False) -> None:
        if only_for_session:
            self._disable_for_session(config_name)
        else:
            disable_in_project(self._window, config_name, only_for_session)
        self.update()

    def _disable_for_session(self, config_name: str) -> None:
        self._disabled_for_session.add(config_name)

    def _reenable_disabled_for_session(self, config_name: str) -> bool:
        if config_name in self._disabled_for_session:
            self._disabled_for_session.remove(config_name)
            return True
        return False
