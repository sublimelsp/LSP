from __future__ import annotations

from .collections import DottedDict
from .logging import debug
from .types import ClientConfig
from .types import debounced
from .types import read_dict_setting
from .types import Settings
from .types import SettingsRegistration
from abc import ABCMeta
from abc import abstractmethod
from typing import Any
import json
import os
import sublime


class LspSettingsChangeListener(metaclass=ABCMeta):

    @abstractmethod
    def on_client_config_updated(self, config_name: str | None = None) -> None:
        raise NotImplementedError()

    @abstractmethod
    def on_userprefs_updated(self) -> None:
        raise NotImplementedError()


class ClientConfigs:

    def __init__(self) -> None:
        self.all: dict[str, ClientConfig] = {}
        self.external: dict[str, ClientConfig] = {}
        self._listener: LspSettingsChangeListener | None = None
        self._clients_hash: int | None = None

    def _notify_clients_listener(self, config_name: str | None = None) -> None:
        if self._listener:
            self._listener.on_client_config_updated(config_name)

    def _notify_userprefs_listener(self) -> None:
        if self._listener:
            self._listener.on_userprefs_updated()

    def add_for_testing(self, config: ClientConfig) -> None:
        assert config.name not in self.all
        self.all[config.name] = config
        self._notify_clients_listener()

    def remove_for_testing(self, config: ClientConfig) -> None:
        self.all.pop(config.name)
        self._notify_clients_listener()

    def add_external_config(self, name: str, s: sublime.Settings, file: str, notify_listener: bool) -> bool:
        if name in self.external:
            return False
        config = ClientConfig.from_sublime_settings(name, s, file)
        self.external[name] = config
        self.all[name] = config
        if notify_listener:
            size = len(self.external)
            # A debounced call is necessary here because of the following problem.
            # When Sublime Text starts, it loads plugins in alphabetical order.
            # Each plugin is loaded 100 milliseconds after the previous plugin.
            # Therefore, we get a sequence of calls to `register_plugin` from all LSP-* helper packages, separated
            # in time intervals of 100 milliseconds.
            # When calling self._notify_listener, we are calling WindowConfigManager.update.
            # That object, in turn, calls WindowConfigManager.update for each window.
            # In turn, each window starts iterating all of its attached views for language servers to attach.
            # That causes many calls to WindowConfigManager.match_view, which is relatively speaking an expensive
            # operation. To ensure that this dance is done only once, we delay notifying the WindowConfigManager until
            # all plugins have done their `register_plugin` call.
            debounced(lambda: self._notify_clients_listener(name), 200, lambda: len(self.external) == size)
        return True

    def remove_external_config(self, name: str) -> None:
        self.external.pop(name, None)
        if self.all.pop(name, None):
            self._notify_clients_listener()

    def update_external_config(self, name: str, s: sublime.Settings, file: str) -> None:
        try:
            config = ClientConfig.from_sublime_settings(name, s, file)
        except OSError:
            # The plugin is about to be disabled (for example by Package Control for an upgrade), let unregister_plugin
            # handle this
            return
        self.external[name] = config
        self.all[name] = config
        self._notify_clients_listener(name)

    def update_configs(self) -> None:
        global _settings_obj
        if _settings_obj is None:
            return
        clients_dict = read_dict_setting(_settings_obj, "clients", {})
        _clients_hash = hash(json.dumps(clients_dict, sort_keys=True))
        if _clients_hash == self._clients_hash:
            self._notify_userprefs_listener()
            return
        self._clients_hash = _clients_hash
        clients = DottedDict(read_dict_setting(_settings_obj, "default_clients", {}))
        clients.update(clients_dict)
        self.all.clear()
        self.all.update({name: ClientConfig.from_dict(name, d) for name, d in clients.get().items()})
        self.all.update(self.external)
        debug("enabled configs:", ", ".join(sorted(c.name for c in self.all.values() if c.enabled)))
        debug("disabled configs:", ", ".join(sorted(c.name for c in self.all.values() if not c.enabled)))
        self._notify_clients_listener()

    def _set_enabled(self, config_name: str, is_enabled: bool) -> None:
        from .sessions import get_plugin
        if plugin := get_plugin(config_name):
            plugin_settings, plugin_settings_name = plugin.configuration()
            settings_basename = os.path.basename(plugin_settings_name)
            plugin_settings.set("enabled", is_enabled)
            sublime.save_settings(settings_basename)
            return
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

    def set_listener(self, listener: LspSettingsChangeListener) -> None:
        self._listener = listener


_settings_obj: sublime.Settings | None = None
_settings: Settings | None = None
_settings_registration: SettingsRegistration | None = None
_global_settings: sublime.Settings | None = None
client_configs = ClientConfigs()


def _on_sublime_settings_changed() -> None:
    if _settings_obj is None or _settings is None:
        return
    _settings.update(_settings_obj)
    client_configs.update_configs()


def load_settings() -> None:
    global _global_settings
    global _settings_obj
    global _settings
    global _settings_registration
    if _global_settings is None:
        _global_settings = sublime.load_settings("Preferences.sublime-settings")
    if _settings_obj is None:
        _settings_obj = sublime.load_settings("LSP.sublime-settings")
        _settings = Settings(_settings_obj)
        _settings_registration = SettingsRegistration(_settings_obj, _on_sublime_settings_changed)


def unload_settings() -> None:
    global _settings_obj
    global _settings
    global _settings_registration
    if _settings_obj is not None:
        _settings_registration = None
        _settings_obj = sublime.load_settings("")
        _settings = Settings(_settings_obj)


def userprefs() -> Settings:
    return _settings  # type: ignore


def globalprefs() -> sublime.Settings:
    return _global_settings  # type: ignore


def read_client_config(name: str, d: dict[str, Any]) -> ClientConfig:
    return ClientConfig.from_dict(name, d)


def update_client_config(external_config: ClientConfig, user_override_config: dict[str, Any]) -> ClientConfig:
    return ClientConfig.from_config(external_config, user_override_config)
