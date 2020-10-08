from .collections import DottedDict
from .logging import debug
from .types import ClientConfig
from .types import read_dict_setting
from .types import Settings
from .types import syntax2scope
from .typing import Any, Optional, Dict, Callable
import sublime

# only used for LSP-* packages out in the wild that now import from "private" modules
# TODO: Announce removal and remove this import
from .types import LanguageConfig  # noqa


PLUGIN_NAME = 'LSP'


class ClientConfigs:

    def __init__(self) -> None:
        self.all = {}  # type: Dict[str, ClientConfig]
        self.external = {}  # type: Dict[str, ClientConfig]
        self._listener = None  # type: Optional[Callable[[], None]]
        self._supported_syntaxes_cache = {}  # type: Dict[str, bool]

    def _notify_listener(self) -> None:
        if callable(self._listener):
            self._listener()

    def add_for_testing(self, config: ClientConfig) -> None:
        assert config.name not in self.all
        self.all[config.name] = config
        self._supported_syntaxes_cache.clear()
        self._notify_listener()

    def remove_for_testing(self, config: ClientConfig) -> None:
        self.all.pop(config.name)
        self._supported_syntaxes_cache.clear()
        self._notify_listener()

    def add_external_config(self, name: str, s: sublime.Settings, file: str) -> None:
        if name in self.external:
            return debug(name, "is already registered")
        config = ClientConfig.from_sublime_settings(name, s, file)
        self.external[name] = config
        self.all[name] = config
        self._notify_listener()

    def remove_external_config(self, name: str) -> None:
        self.external.pop(name, None)
        if self.all.pop(name, None):
            self._notify_listener()
        else:
            debug(name, "was not registered")

    def update_configs(self) -> None:
        global _settings_obj
        if _settings_obj is None:
            return
        clients = DottedDict(read_dict_setting(_settings_obj, "default_clients", {}))
        clients.update(read_dict_setting(_settings_obj, "clients", {}))
        self._supported_syntaxes_cache.clear()
        self.all.clear()
        self.all.update({name: ClientConfig.from_dict(name, d) for name, d in clients.get().items()})
        self.all.update(self.external)
        debug("enabled configs:", ", ".join(sorted(c.name for c in self.all.values() if c.enabled)))
        debug("disabled configs:", ", ".join(sorted(c.name for c in self.all.values() if not c.enabled)))
        self._notify_listener()

    def _set_enabled(self, config_name: str, is_enabled: bool) -> None:
        settings = sublime.load_settings("LSP.sublime-settings")
        clients = settings.get("clients")
        if isinstance(clients, dict):
            config = clients.setdefault(config_name, {})
            config["enabled"] = is_enabled
            settings.set("clients", clients)
            sublime.save_settings("LSP.sublime-settings")

    def enable(self, config_name: str) -> None:
        self._set_enabled(config_name, True)

    def disable(self, config_name: str) -> None:
        self._set_enabled(config_name, False)

    def set_listener(self, recipient: Callable[[], None]) -> None:
        self._listener = recipient

    def is_syntax_supported(self, syntax: str) -> bool:
        if syntax in self._supported_syntaxes_cache:
            return self._supported_syntaxes_cache[syntax]
        scope = syntax2scope(syntax)
        supported = bool(scope and any(config.match_scope(scope) for config in self.all.values()))
        self._supported_syntaxes_cache[syntax] = supported
        return supported


_settings_obj = None  # type: Optional[sublime.Settings]
_settings = None  # type: Optional[Settings]
client_configs = ClientConfigs()


def _on_sublime_settings_changed() -> None:
    global _settings_obj
    global _settings
    global client_configs
    if _settings_obj is None or _settings is None:
        return
    _settings.update(_settings_obj)
    client_configs.update_configs()


def load_settings() -> None:
    global _settings_obj
    global _settings
    global client_configs
    if _settings_obj is None:
        _settings_obj = sublime.load_settings("LSP.sublime-settings")
        _settings = Settings(_settings_obj)
        _settings_obj.add_on_change("LSP", _on_sublime_settings_changed)


def unload_settings() -> None:
    global _settings_obj
    global _settings
    if _settings_obj is not None:
        _settings_obj.clear_on_change("LSP")
        _settings_obj = None


def userprefs() -> Settings:
    global _settings
    return _settings  # type: ignore


def read_client_config(name: str, d: Dict[str, Any]) -> ClientConfig:
    return ClientConfig.from_dict(name, d)


def update_client_config(external_config: ClientConfig, user_override_config: Dict[str, Any]) -> ClientConfig:
    return external_config.update(user_override_config)
