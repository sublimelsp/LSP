from __future__ import annotations
from .logging import debug
from .logging import exception_log
from .logging import printf
from .types import ClientConfig
from .url import parse_uri
from .workspace import enable_in_project, disable_in_project
from abc import ABCMeta
from abc import abstractmethod
from collections import deque
from datetime import datetime, timedelta
from typing import Generator
from weakref import WeakSet
import sublime


RETRY_MAX_COUNT = 5
RETRY_COUNT_TIMEDELTA = timedelta(minutes=3)


class WindowConfigChangeListener(metaclass=ABCMeta):

    @abstractmethod
    def on_configs_changed(self, configs: list[ClientConfig]) -> None:
        raise NotImplementedError


class WindowConfigManager:
    def __init__(self, window: sublime.Window, global_configs: dict[str, ClientConfig]) -> None:
        self._window = window
        self._global_configs = global_configs
        self._disabled_for_session: set[str] = set()
        self._crashes: dict[str, deque[datetime]] = {}
        self.all: dict[str, ClientConfig] = {}
        self._change_listeners: WeakSet[WindowConfigChangeListener] = WeakSet()
        self._reload_configs(notify_listeners=False)

    def add_change_listener(self, listener: WindowConfigChangeListener) -> None:
        self._change_listeners.add(listener)

    def get_config(self, config_name: str) -> ClientConfig | None:
        return self.all.get(config_name)

    def get_configs(self) -> list[ClientConfig]:
        return sorted(self.all.values(), key=lambda config: config.name)

    def match_view(self, view: sublime.View, include_disabled: bool = False) -> Generator[ClientConfig, None, None]:
        """
        Yields configurations where:

        - the configuration's "selector" matches with the view's base scope, and
        - the view's URI scheme is an element of the configuration's "schemes".
        """
        try:
            uri = view.settings().get("lsp_uri")
            if not isinstance(uri, str):
                return
            scheme = parse_uri(uri)[0]
            for config in self.all.values():
                if (config.enabled or include_disabled) and config.match_view(view, scheme):
                    yield config
        except (IndexError, RuntimeError):
            pass

    def update(self, updated_config_name: str | None = None) -> None:
        self._reload_configs(updated_config_name, notify_listeners=True)

    def _reload_configs(self, updated_config_name: str | None = None, notify_listeners: bool = False) -> None:
        project_data = self._window.project_data()
        project_settings = project_data.get("settings", {}).get("LSP", {}) if isinstance(project_data, dict) else {}
        updated_configs: list[ClientConfig] = []
        if updated_config_name is None:
            self.all.clear()
        for name, config in self._global_configs.items():
            if updated_config_name and updated_config_name != name:
                continue
            overrides = project_settings.pop(name, None)
            if isinstance(overrides, dict):
                debug("applying .sublime-project override for", name)
            else:
                overrides = {}
            if name in self._disabled_for_session:
                overrides["enabled"] = False
            updated_config = ClientConfig.from_config(config, overrides)
            self.all[name] = updated_config
            updated_configs.append(updated_config)
        for name, c in project_settings.items():
            if updated_config_name and updated_config_name != name:
                continue
            debug("loading project-only configuration", name)
            try:
                updated_config = ClientConfig.from_dict(name, c)
                self.all[name] = updated_config
                updated_configs.append(updated_config)
            except Exception as ex:
                exception_log(f"failed to load project-only configuration {name}", ex)
        if notify_listeners:
            for listener in self._change_listeners:
                listener.on_configs_changed(updated_configs)

    def enable_config(self, config_name: str) -> None:
        if not self._reenable_disabled_for_session(config_name):
            enable_in_project(self._window, config_name)
        self.update(config_name)

    def disable_config(self, config_name: str, only_for_session: bool = False) -> None:
        if only_for_session:
            self._disabled_for_session.add(config_name)
        else:
            disable_in_project(self._window, config_name)
        self.update(config_name)

    def record_crash(self, config_name: str, exit_code: int, exception: Exception | None) -> bool:
        """
        Signal that a session has crashed.

        Returns True if the session should be restarted automatically.
        """
        if config_name not in self._crashes:
            self._crashes[config_name] = deque(maxlen=RETRY_MAX_COUNT)
        now = datetime.now()
        self._crashes[config_name].append(now)
        timeout = now - RETRY_COUNT_TIMEDELTA
        crash_count = len([crash for crash in self._crashes[config_name] if crash > timeout])
        printf("{} crashed ({} / {} times in the last {} seconds), exit code {}, exception: {}".format(
            config_name, crash_count, RETRY_MAX_COUNT, RETRY_COUNT_TIMEDELTA.total_seconds(), exit_code, exception))
        return crash_count < RETRY_MAX_COUNT

    def _reenable_disabled_for_session(self, config_name: str) -> bool:
        try:
            self._disabled_for_session.remove(config_name)
            return True
        except KeyError:
            return False
