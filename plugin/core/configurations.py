from __future__ import annotations

from .logging import exception_log
from .logging import printf
from .types import ClientConfig
from .url import parse_uri
from .workspace import disable_in_project
from .workspace import enable_in_project
from .workspace import WorkspaceFolder
from abc import ABC
from abc import abstractmethod
from collections import deque
from datetime import datetime
from datetime import timedelta
from typing import Generator
from typing import Literal
from typing import TYPE_CHECKING
from weakref import WeakSet

if TYPE_CHECKING:
    import sublime

RETRY_MAX_COUNT = 5
RETRY_COUNT_TIMEDELTA = timedelta(minutes=3)


ConfigChangeType = Literal['added', 'removed', 'root_changed', 'settings_changed', 'unchanged']


class WindowConfigChangeListener(ABC):

    @abstractmethod
    def on_configs_changed(self, configs: list[ClientConfig]) -> None:
        raise NotImplementedError

    @abstractmethod
    def on_server_settings_changed(self, configs: list[ClientConfig]) -> None:
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

    def match_view(self, view: sublime.View, workspace_folders: list[WorkspaceFolder]) -> Generator[ClientConfig]:
        """
        Yields matching configuration.

        Matches if:
        - the configuration's "selector" matches with the view's base scope, and
        - the view's URI scheme is an element of the configuration's "schemes".
        """
        try:
            uri = view.settings().get("lsp_uri")
            if not isinstance(uri, str):
                return
            scheme = parse_uri(uri)[0]
            for config in self.all.values():
                if config.enabled and config.match_view(view, scheme, self._window, workspace_folders):
                    yield config
        except (IndexError, RuntimeError):
            pass

    def update(self, updated_config_name: str | None = None) -> None:
        self._reload_configs(updated_config_name, notify_listeners=True)

    def _reload_configs(self, updated_config_name: str | None = None, notify_listeners: bool = False) -> None:
        project_data = self._window.project_data()
        project_settings = project_data.get("settings", {}).get("LSP", {}) if isinstance(project_data, dict) else {}

        def resolve_configs(updated_config_name: str | None = None) -> Generator[tuple[ConfigChangeType, ClientConfig]]:
            seen_config_names: set[str] = set()
            for name, config in self._global_configs.items():
                if updated_config_name and updated_config_name != name:
                    continue
                overrides = project_settings.pop(name, None)
                if not isinstance(overrides, dict):
                    overrides = {}
                if name in self._disabled_for_session:
                    overrides["enabled"] = False
                stored_config = self.all.get(name)
                updated_config = ClientConfig.from_config(config, overrides)
                seen_config_names.add(name)
                yield compare_configs(stored_config, updated_config)
            for name, config in project_settings.items():
                if updated_config_name and updated_config_name != name:
                    continue
                if name in self._disabled_for_session:
                    config["enabled"] = False
                try:
                    updated_config = ClientConfig.from_dict(name, config)
                except Exception as ex:
                    updated_config = None
                    exception_log(f"failed to load project-only configuration {name}", ex)
                if updated_config:
                    stored_config = self.all.get(name)
                    yield compare_configs(stored_config, updated_config)
                seen_config_names.add(name)
            # Configs in "all" that were not seen are gone.
            removed_names = self.all.keys() - seen_config_names
            for name in removed_names:
                yield ('removed', self.all[name])

        def compare_configs(
            old_config: ClientConfig | None, new_config: ClientConfig
        ) -> tuple[ConfigChangeType, ClientConfig]:
            if old_config:
                if old_config != new_config:
                    return ('root_changed', new_config)
                if old_config.settings != new_config.settings:
                    return ('settings_changed', new_config)
                return ('unchanged', old_config)
            return ('added', new_config)

        changes: dict[ConfigChangeType, list[ClientConfig]] = {
            'added': [],
            'removed': [],
            'root_changed': [],
            'settings_changed': [],
            'unchanged': []
        }
        if updated_config_name:
            if result := next(resolve_configs(updated_config_name), None):
                change_type, config = result
                changes[change_type].append(config)
                self.all[config.name] = config
        else:
            for result in resolve_configs():
                change_type, config = result
                changes[change_type].append(config)
            self.all = {
                **{c.name: c for c in changes['root_changed']},
                **{c.name: c for c in changes['settings_changed']},
                **{c.name: c for c in changes['unchanged']},
                **{c.name: c for c in changes['added']},
            }
        if notify_listeners:
            if changed := changes['settings_changed']:
                for listener in self._change_listeners:
                    listener.on_server_settings_changed(changed)
            if changed := changes['root_changed'] + changes['removed']:
                for listener in self._change_listeners:
                    listener.on_configs_changed(changed)

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
        printf(f"{config_name} crashed ({crash_count} / {RETRY_MAX_COUNT} times in the last "
               f"{RETRY_COUNT_TIMEDELTA.total_seconds()} seconds), exit code {exit_code}, exception: {exception}")
        return crash_count < RETRY_MAX_COUNT

    def _reenable_disabled_for_session(self, config_name: str) -> bool:
        try:
            self._disabled_for_session.remove(config_name)
        except KeyError:
            return False
        return True
