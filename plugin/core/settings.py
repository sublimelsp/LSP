import sublime
from .types import Settings

PLUGIN_NAME = 'LSP'

try:
    from typing import List, Optional, Dict
    assert List and Optional and Dict
except ImportError:
    pass


def read_bool_setting(settings_obj: sublime.Settings, key: str, default: bool) -> bool:
    val = settings_obj.get(key)
    if isinstance(val, bool):
        return val
    else:
        return default


def read_int_setting(settings_obj: sublime.Settings, key: str, default: int) -> int:
    val = settings_obj.get(key)
    if isinstance(val, int):
        return val
    else:
        return default


def read_dict_setting(settings_obj: sublime.Settings, key: str, default: dict) -> dict:
    val = settings_obj.get(key)
    if isinstance(val, dict):
        return val
    else:
        return default


def read_str_setting(settings_obj: sublime.Settings, key: str, default: str) -> str:
    val = settings_obj.get(key)
    if isinstance(val, str):
        return val
    else:
        return default


def update_settings(settings: Settings, settings_obj: sublime.Settings):
    settings.show_status_messages = read_bool_setting(settings_obj, "show_status_messages", True)
    settings.show_view_status = read_bool_setting(settings_obj, "show_view_status", True)
    settings.auto_show_diagnostics_panel = read_bool_setting(settings_obj, "auto_show_diagnostics_panel", True)
    settings.show_diagnostics_phantoms = read_bool_setting(settings_obj, "show_diagnostics_phantoms", False)
    settings.show_diagnostics_count_in_view_status = read_bool_setting(settings_obj,
                                                                       "show_diagnostics_count_in_view_status", False)
    settings.show_diagnostics_in_view_status = read_bool_setting(settings_obj, "show_diagnostics_in_view_status", True)
    settings.show_diagnostics_severity_level = read_int_setting(settings_obj, "show_diagnostics_severity_level", 3)
    settings.diagnostics_highlight_style = read_str_setting(settings_obj, "diagnostics_highlight_style", "underline")
    settings.highlight_active_signature_parameter = read_bool_setting(settings_obj,
                                                                      "highlight_active_signature_parameter", True)
    settings.document_highlight_style = read_str_setting(settings_obj, "document_highlight_style", "stippled")
    settings.document_highlight_scopes = read_dict_setting(settings_obj, "document_highlight_scopes",
                                                           settings.document_highlight_scopes)
    settings.diagnostics_gutter_marker = read_str_setting(settings_obj, "diagnostics_gutter_marker", "dot")
    settings.only_show_lsp_completions = read_bool_setting(settings_obj, "only_show_lsp_completions", False)
    settings.complete_all_chars = read_bool_setting(settings_obj, "complete_all_chars", True)
    settings.completion_hint_type = read_str_setting(settings_obj, "completion_hint_type", "auto")
    settings.resolve_completion_for_snippets = read_bool_setting(settings_obj, "resolve_completion_for_snippets", False)
    settings.log_debug = read_bool_setting(settings_obj, "log_debug", False)
    settings.log_server = read_bool_setting(settings_obj, "log_server", True)
    settings.log_stderr = read_bool_setting(settings_obj, "log_stderr", False)
    settings.log_payloads = read_bool_setting(settings_obj, "log_payloads", False)


class ClientConfig(object):
    def __init__(self, name, binary_args, tcp_port, scopes, syntaxes, languageId,
                 enabled=True, init_options=dict(), settings=dict(), env=dict()):
        self.name = name
        self.binary_args = binary_args
        self.tcp_port = tcp_port
        self.scopes = scopes
        self.syntaxes = syntaxes
        self.languageId = languageId
        self.enabled = enabled
        self.init_options = init_options
        self.settings = settings
        self.env = env

    def apply_settings(self, settings: dict) -> None:
        if "command" in settings:
            self.binary_args = settings.get("command", [])
        if "tcp_port" in settings:
            self.tcp_port = settings.get("tcp_port", None)
        if "scopes" in settings:
            self.scopes = settings.get("scopes", [])
        if "syntaxes" in settings:
            self.syntaxes = settings.get("syntaxes", [])
        if "languageId" in settings:
            self.languageId = settings.get("languageId", "")
        if "enabled" in settings:
            self.enabled = settings.get("enabled", True)
        if "initializationOptions" in settings:
            self.init_options = settings.get("initializationOptions", dict())
        if "settings" in settings:
            self.settings = settings.get("settings", dict())
        if "env" in settings:
            self.env = settings.get("env", dict())


class ClientConfigs(object):

    def __init__(self):
        self._default_settings = dict()  # type: Dict[str, dict]
        self._global_settings = dict()  # type: Dict[str, dict]
        self.defaults = []  # type: List[ClientConfig]
        self.all = []  # type: List[ClientConfig]
        self._external_configs = []  # type: List[ClientConfig]

    def update(self, settings_obj: sublime.Settings):
        self._default_settings = read_dict_setting(settings_obj, "default_clients", {})
        self._global_settings = read_dict_setting(settings_obj, "clients", {})

        self.defaults = read_client_configs(self._default_settings)
        self.all = read_client_configs(self._global_settings, self._default_settings)
        for config in self._external_configs:
            if config.name in self._global_settings:
                config.apply_settings(self._global_settings[config.name])
        self.all.extend(self._external_configs)

    def add_external_config(self, config: ClientConfig):
        print('adding ', config.name)
        if config.name in self._global_settings:
            config.apply_settings(self._global_settings[config.name])
        self._external_configs.append(config)
        self.all.append(config)

    def _set_enabled(self, config_name: str, is_enabled: bool):
        if _settings_obj:
            client_settings = self._global_settings.setdefault(config_name, {})
            client_settings["enabled"] = is_enabled
            _settings_obj.set("clients", self._global_settings)
            sublime.save_settings("LSP.sublime-settings")

    def enable(self, config_name: str):
        self._set_enabled(config_name, True)

    def disable(self, config_name: str):
        self._set_enabled(config_name, False)


_settings_obj = None  # type: Optional[sublime.Settings]
settings = Settings()
client_configs = ClientConfigs()


def load_settings():
    global _settings_obj
    loaded_settings_obj = sublime.load_settings("LSP.sublime-settings")
    _settings_obj = loaded_settings_obj
    update_settings(settings, loaded_settings_obj)
    client_configs.update(loaded_settings_obj)
    loaded_settings_obj.add_on_change("_on_new_settings", lambda: update_settings(settings, loaded_settings_obj))
    loaded_settings_obj.add_on_change("_on_new_client_settings", lambda: client_configs.update(loaded_settings_obj))


def unload_settings():
    if _settings_obj:
        _settings_obj.clear_on_change("_on_new_settings")
        _settings_obj.clear_on_change("_on_new_client_settings")


def read_client_config(name, client_config):
    return ClientConfig(
        name,
        client_config.get("command", []),
        client_config.get("tcp_port", None),
        client_config.get("scopes", []),
        client_config.get("syntaxes", []),
        client_config.get("languageId", ""),
        client_config.get("enabled", True),
        client_config.get("initializationOptions", dict()),
        client_config.get("settings", dict()),
        client_config.get("env", dict())
    )


def read_client_configs(client_settings, default_client_settings=None) -> 'List[ClientConfig]':
    parsed_configs = []  # type: List[ClientConfig]
    if isinstance(client_settings, dict):
        for client_name, client_config in client_settings.items():

            # start with default settings for this client if available
            client_with_defaults = {}  # type: Dict[str, dict]
            if default_client_settings and client_name in default_client_settings:
                client_with_defaults = default_client_settings[client_name]
            client_with_defaults.update(client_config)

            config = read_client_config(client_name, client_with_defaults)
            if config and config.scopes:  # don't return configs only containing "enabled" here.
                parsed_configs.append(config)
        return parsed_configs
    else:
        raise ValueError("configs")
