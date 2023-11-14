from .logging import debug
from .logging import exception_log
from .logging import printf
from .types import ClientConfig
from .typing import Generator, List, Optional, Set, Dict, Deque
from .url import parse_uri
from .workspace import enable_in_project, disable_in_project
from abc import ABCMeta
from abc import abstractmethod
from collections import deque
from datetime import datetime, timedelta
from weakref import WeakSet
import sublime


RETRY_MAX_COUNT = 5
RETRY_COUNT_TIMEDELTA = timedelta(minutes=3)


class WindowConfigChangeListener(metaclass=ABCMeta):

    @abstractmethod
    def on_configs_changed(self, config_name: Optional[str] = None) -> None:
        raise NotImplementedError()


class WindowConfigManager(object):
    def __init__(self, window: sublime.Window, global_configs: Dict[str, ClientConfig]) -> None:
        self._window = window
        self._global_configs = global_configs
        self._disabled_for_session = set()  # type: Set[str]
        self._crashes = {}  # type: Dict[str, Deque[datetime]]
        self.all = {}  # type: Dict[str, ClientConfig]
        self._change_listeners = WeakSet()  # type: WeakSet[WindowConfigChangeListener]
        self._reload_configs(notify_listeners=False)

    def add_change_listener(self, listener: WindowConfigChangeListener) -> None:
        self._change_listeners.add(listener)

    def get_configs(self) -> List[ClientConfig]:
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
                if config.match_view(view, scheme) and (config.enabled or include_disabled):
                    yield config
        except (IndexError, RuntimeError):
            pass

    def update(self, updated_config_name: Optional[str] = None) -> None:
        self._reload_configs(updated_config_name, notify_listeners=True)

    def _reload_configs(self, updated_config_name: Optional[str] = None, notify_listeners: bool = False) -> None:
        project_settings = (self._window.project_data() or {}).get("settings", {}).get("LSP", {})
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
            self.all[name] = ClientConfig.from_config(config, overrides)
        for name, c in project_settings.items():
            if updated_config_name and updated_config_name != name:
                continue
            debug("loading project-only configuration", name)
            try:
                self.all[name] = ClientConfig.from_dict(name, c)
            except Exception as ex:
                exception_log("failed to load project-only configuration {}".format(name), ex)
        if notify_listeners:
            for listener in self._change_listeners:
                listener.on_configs_changed(updated_config_name)

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

    def record_crash(self, config_name: str, exit_code: int, exception: Optional[Exception]) -> bool:
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
