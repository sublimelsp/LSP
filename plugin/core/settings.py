import sublime

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


class Settings(object):

    def __init__(self):
        self.show_status_messages = True
        self.show_view_status = True
        self.auto_show_diagnostics_panel = True
        self.show_diagnostics_phantoms = False
        self.show_diagnostics_in_view_status = True
        self.only_show_lsp_completions = False
        self.diagnostics_highlight_style = "underline"
        self.highlight_active_signature_parameter = True
        self.document_highlight_style = "stippled"
        self.document_highlight_scopes = {
            "unknown": "text",
            "text": "text",
            "read": "markup.inserted",
            "write": "markup.changed"
        }
        self.diagnostics_gutter_marker = "dot"
        self.complete_all_chars = False
        self.completion_hint_type = "auto"
        self.resolve_completion_for_snippets = False
        self.log_debug = True
        self.log_server = True
        self.log_stderr = False
        self.log_payloads = False

    def update(self, settings_obj: sublime.Settings):
        self.show_status_messages = read_bool_setting(settings_obj, "show_status_messages", True)
        self.show_view_status = read_bool_setting(settings_obj, "show_view_status", True)
        self.auto_show_diagnostics_panel = read_bool_setting(settings_obj, "auto_show_diagnostics_panel", True)
        self.show_diagnostics_phantoms = read_bool_setting(settings_obj, "show_diagnostics_phantoms", False)
        self.show_diagnostics_in_view_status = read_bool_setting(settings_obj, "show_diagnostics_in_view_status", True)
        self.diagnostics_highlight_style = read_str_setting(settings_obj, "diagnostics_highlight_style", "underline")
        self.highlight_active_signature_parameter = read_bool_setting(settings_obj,
                                                                      "highlight_active_signature_parameter", True)
        self.document_highlight_style = read_str_setting(settings_obj, "document_highlight_style", "stippled")
        self.document_highlight_scopes = read_dict_setting(settings_obj, "document_highlight_scopes",
                                                           self.document_highlight_scopes)
        self.diagnostics_gutter_marker = read_str_setting(settings_obj, "diagnostics_gutter_marker", "dot")
        self.only_show_lsp_completions = read_bool_setting(settings_obj, "only_show_lsp_completions", False)
        self.complete_all_chars = read_bool_setting(settings_obj, "complete_all_chars", True)
        self.completion_hint_type = read_str_setting(settings_obj, "completion_hint_type", "auto")
        self.resolve_completion_for_snippets = read_bool_setting(settings_obj, "resolve_completion_for_snippets", False)
        self.log_debug = read_bool_setting(settings_obj, "log_debug", False)
        self.log_server = read_bool_setting(settings_obj, "log_server", True)
        self.log_stderr = read_bool_setting(settings_obj, "log_stderr", False)
        self.log_payloads = read_bool_setting(settings_obj, "log_payloads", False)


class ClientConfigs(object):

    def __init__(self):
        self._default_settings = dict()  # type: Dict[str, dict]
        self._global_settings = dict()  # type: Dict[str, dict]
        self.defaults = []  # type: List[ClientConfig]
        self.all = []  # type: List[ClientConfig]

    def update(self, settings_obj: sublime.Settings):
        self._default_settings = read_dict_setting(settings_obj, "default_clients", {})
        self._global_settings = read_dict_setting(settings_obj, "clients", {})

        self.defaults = read_client_configs(self._default_settings)
        self.all = read_client_configs(self._global_settings, self._default_settings)

        client_enableds = list("=".join([config.name, str(config.enabled)]) for config in self.all)
        print(PLUGIN_NAME + ': global clients: ' + ", ".join(client_enableds))

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
    settings.update(loaded_settings_obj)
    client_configs.update(loaded_settings_obj)
    loaded_settings_obj.add_on_change("_on_new_settings", lambda: settings.update(loaded_settings_obj))
    loaded_settings_obj.add_on_change("_on_new_client_settings", lambda: client_configs.update(loaded_settings_obj))


def unload_settings():
    if _settings_obj:
        _settings_obj.clear_on_change("_on_new_settings")
        _settings_obj.clear_on_change("_on_new_client_settings")


class ClientConfig(object):
    def __init__(self, name, binary_args, scopes, syntaxes, languageId,
                 enabled=True, init_options=dict(), settings=dict(), env=dict()):
        self.name = name
        self.binary_args = binary_args
        self.scopes = scopes
        self.syntaxes = syntaxes
        self.languageId = languageId
        self.enabled = enabled
        self.init_options = init_options
        self.settings = settings
        self.env = env


def read_client_config(name, client_config):
    return ClientConfig(
        name,
        client_config.get("command", []),
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
            if config:
                parsed_configs.append(config)
        return parsed_configs
    else:
        raise ValueError("configs")
