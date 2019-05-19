import sublime
from .types import Settings, ClientConfig, LanguageConfig
from .logging import debug

PLUGIN_NAME = 'LSP'

try:
    from typing import List, Optional, Dict, Any
    assert List and Optional and Dict and Any
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
    settings.show_view_status = read_bool_setting(settings_obj, "show_view_status", True)
    settings.auto_show_diagnostics_panel = read_bool_setting(settings_obj, "auto_show_diagnostics_panel", True)
    settings.auto_show_diagnostics_panel_level = read_int_setting(settings_obj, "auto_show_diagnostics_panel_level", 3)
    settings.show_diagnostics_phantoms = read_bool_setting(settings_obj, "show_diagnostics_phantoms", False)
    settings.show_diagnostics_count_in_view_status = read_bool_setting(settings_obj,
                                                                       "show_diagnostics_count_in_view_status", False)
    settings.show_diagnostics_in_view_status = read_bool_setting(settings_obj, "show_diagnostics_in_view_status", True)
    settings.show_diagnostics_severity_level = read_int_setting(settings_obj, "show_diagnostics_severity_level", 3)
    settings.diagnostics_highlight_style = read_str_setting(settings_obj, "diagnostics_highlight_style", "underline")
    settings.document_highlight_style = read_str_setting(settings_obj, "document_highlight_style", "stippled")
    settings.document_highlight_scopes = read_dict_setting(settings_obj, "document_highlight_scopes",
                                                           settings.document_highlight_scopes)
    settings.diagnostics_gutter_marker = read_str_setting(settings_obj, "diagnostics_gutter_marker", "dot")
    settings.show_code_actions_bulb = read_bool_setting(settings_obj, "show_code_actions_bulb", False)
    settings.only_show_lsp_completions = read_bool_setting(settings_obj, "only_show_lsp_completions", False)
    settings.complete_all_chars = read_bool_setting(settings_obj, "complete_all_chars", True)
    settings.completion_hint_type = read_str_setting(settings_obj, "completion_hint_type", "auto")
    settings.prefer_label_over_filter_text = read_bool_setting(settings_obj, "prefer_label_over_filter_text", False)
    settings.show_references_in_quick_panel = read_bool_setting(settings_obj, "show_references_in_quick_panel", False)
    settings.quick_panel_monospace_font = read_bool_setting(settings_obj, "quick_panel_monospace_font", False)
    settings.log_debug = read_bool_setting(settings_obj, "log_debug", False)
    settings.log_server = read_bool_setting(settings_obj, "log_server", True)
    settings.log_stderr = read_bool_setting(settings_obj, "log_stderr", False)
    settings.log_payloads = read_bool_setting(settings_obj, "log_payloads", False)


class ClientConfigs(object):

    def __init__(self):
        self._default_settings = dict()  # type: Dict[str, dict]
        self._global_settings = dict()  # type: Dict[str, dict]
        self._external_configs = dict()  # type: Dict[str, ClientConfig]
        self.all = []  # type: List[ClientConfig]

    def update(self, settings_obj: sublime.Settings):
        self._default_settings = read_dict_setting(settings_obj, "default_clients", {})
        self._global_settings = read_dict_setting(settings_obj, "clients", {})
        self.update_configs()

    def add_external_config(self, config: ClientConfig):
        self._external_configs[config.name] = config

    def update_configs(self):
        del self.all[:]

        for config_name, config in self._external_configs.items():
            user_settings = self._global_settings.get(config_name, dict())
            global_config = update_client_config(config, user_settings)
            self.all.append(global_config)

        all_config_names = set(self._default_settings) | set(self._global_settings)
        for config_name in all_config_names.difference(set(self._external_configs)):
            merged_settings = self._default_settings.get(config_name, dict())
            user_settings = self._global_settings.get(config_name, dict())
            merged_settings.update(user_settings)
            self.all.append(read_client_config(config_name, merged_settings))

        debug('global configs', list('{}={}'.format(c.name, c.enabled) for c in self.all))

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


def read_language_config(config: dict) -> 'LanguageConfig':
    language_id = config.get("languageId", "")
    scopes = config.get("scopes", [])
    syntaxes = config.get("syntaxes", [])
    return LanguageConfig(language_id, scopes, syntaxes)


def read_language_configs(client_config: dict) -> 'List[LanguageConfig]':
    return list(map(read_language_config, client_config.get("languages", [])))


def read_client_config(name: str, client_config: 'Dict') -> ClientConfig:
    languages = read_language_configs(client_config)

    return ClientConfig(
        name,
        client_config.get("command", []),
        client_config.get("tcp_port", None),
        client_config.get("scopes", []),
        client_config.get("syntaxes", []),
        client_config.get("languageId", ""),
        languages,
        client_config.get("enabled", False),
        client_config.get("initializationOptions", dict()),
        client_config.get("settings", dict()),
        client_config.get("env", dict()),
        client_config.get("tcp_host", None)
    )


def update_client_config(config: 'ClientConfig', settings: dict) -> 'ClientConfig':
    default_language = config.languages[0]
    return ClientConfig(
        config.name,
        settings.get("command", config.binary_args),
        settings.get("tcp_port", config.tcp_port),
        settings.get("scopes", default_language.scopes),
        settings.get("syntaxes", default_language.syntaxes),
        settings.get("languageId", default_language.id),
        read_language_configs(settings) or config.languages,
        settings.get("enabled", config.enabled),
        settings.get("init_options", config.init_options),
        settings.get("settings", config.settings),
        settings.get("env", config.env),
        settings.get("tcp_host", config.tcp_host)
    )
