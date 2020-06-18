from .collections import DottedDict
from .logging import debug
from .types import Settings, ClientConfig, LanguageConfig, syntax2scope
from .typing import Any, List, Optional, Dict, Callable, Union
from copy import deepcopy
import sublime


PLUGIN_NAME = 'LSP'


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


def read_array_setting(settings_obj: sublime.Settings, key: str, default: list) -> list:
    val = settings_obj.get(key)
    if isinstance(val, list):
        return val
    else:
        return default


def read_str_setting(settings_obj: sublime.Settings, key: str, default: str) -> str:
    val = settings_obj.get(key)
    if isinstance(val, str):
        return val
    else:
        return default


def read_auto_show_diagnostics_panel_setting(settings_obj: sublime.Settings, key: str, default: str) -> str:
    val = settings_obj.get(key)
    if isinstance(val, bool):
        return 'always' if val else 'never'
    if isinstance(val, str):
        return val
    else:
        return default


def update_settings(settings: Settings, settings_obj: sublime.Settings) -> None:
    settings.show_view_status = read_bool_setting(settings_obj, "show_view_status", True)
    settings.auto_show_diagnostics_panel = read_auto_show_diagnostics_panel_setting(settings_obj,
                                                                                    "auto_show_diagnostics_panel",
                                                                                    'always')
    settings.auto_show_diagnostics_panel_level = read_int_setting(settings_obj, "auto_show_diagnostics_panel_level", 2)
    settings.show_diagnostics_count_in_view_status = read_bool_setting(settings_obj,
                                                                       "show_diagnostics_count_in_view_status", False)
    settings.show_diagnostics_in_view_status = read_bool_setting(settings_obj, "show_diagnostics_in_view_status", True)
    settings.show_diagnostics_severity_level = read_int_setting(settings_obj, "show_diagnostics_severity_level", 2)
    settings.diagnostics_highlight_style = read_str_setting(settings_obj, "diagnostics_highlight_style", "underline")
    settings.document_highlight_style = read_str_setting(settings_obj, "document_highlight_style", "stippled")
    settings.document_highlight_scopes = read_dict_setting(settings_obj, "document_highlight_scopes",
                                                           settings.document_highlight_scopes)
    settings.diagnostics_gutter_marker = read_str_setting(settings_obj, "diagnostics_gutter_marker", "dot")
    settings.show_symbol_action_links = read_bool_setting(settings_obj, "show_symbol_action_links", False)
    settings.only_show_lsp_completions = read_bool_setting(settings_obj, "only_show_lsp_completions", False)
    settings.show_references_in_quick_panel = read_bool_setting(settings_obj, "show_references_in_quick_panel", False)
    settings.disabled_capabilities = read_array_setting(settings_obj, "disabled_capabilities", [])
    settings.log_debug = read_bool_setting(settings_obj, "log_debug", False)
    settings.log_server = read_bool_setting(settings_obj, "log_server", False)
    settings.log_stderr = read_bool_setting(settings_obj, "log_stderr", False)
    settings.lsp_format_on_save = read_bool_setting(settings_obj, "lsp_format_on_save", False)
    settings.lsp_code_actions_on_save = read_dict_setting(settings_obj, "lsp_code_actions_on_save", {})
    settings.code_action_on_save_timeout_ms = read_int_setting(settings_obj, "code_action_on_save_timeout_ms", 2000)


class ClientConfigs(object):

    def __init__(self) -> None:
        self._default_settings = dict()  # type: Dict[str, dict]
        self._global_settings = dict()  # type: Dict[str, dict]
        self._external_configs = dict()  # type: Dict[str, ClientConfig]
        self.all = []  # type: List[ClientConfig]
        self._listener = None  # type: Optional[Callable]
        self._supported_syntaxes_cache = dict()  # type: Dict[str, bool]

    def update(self, settings_obj: sublime.Settings, also_update_configs: bool = False) -> None:
        self._default_settings = read_dict_setting(settings_obj, "default_clients", {})
        self._global_settings = read_dict_setting(settings_obj, "clients", {})
        if also_update_configs:
            self.update_configs()

    def add_for_testing(self, config: ClientConfig) -> None:
        self.all.append(config)
        self._supported_syntaxes_cache = dict()
        if self._listener:
            self._listener()

    def remove_for_testing(self, config: ClientConfig) -> None:
        self.all.remove(config)
        self._supported_syntaxes_cache = dict()
        if self._listener:
            self._listener()

    def add_external_config(self, name: str, s: sublime.Settings, file: str) -> None:
        base = sublime.decode_value(sublime.load_resource(file))
        settings = DottedDict(base.get("settings", {}))  # defined by the plugin author
        settings.update(read_dict_setting(s, "settings", {}))  # overrides from the user
        config = ClientConfig(
            name=name,
            binary_args=read_array_setting(s, "command", []),
            languages=read_language_configs(s),
            tcp_port=s.get("tcp_port", None),
            # Default to True, because an LSP plugin is enabled iff it is enabled as a Sublime package.
            enabled=bool(s.get("enabled", True)),
            init_options=s.get("initializationOptions"),  # type: ignore
            settings=settings,
            env=read_dict_setting(s, "env", {}),
            tcp_host=s.get("tcp_host", None),
            tcp_mode=s.get("tcp_mode", None),
            experimental_capabilities=s.get("experimental_capabilities", None)  # type: ignore
        )
        self._external_configs[config.name] = config

    def remove_external_config(self, name: str) -> None:
        self._external_configs.pop(name, None)

    def update_configs(self) -> None:
        del self.all[:]
        self._supported_syntaxes_cache = dict()

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
        if self._listener:
            self._listener()

    def _set_enabled(self, config_name: str, is_enabled: bool) -> None:
        if _settings_obj:
            client_settings = self._global_settings.setdefault(config_name, {})
            client_settings["enabled"] = is_enabled
            _settings_obj.set("clients", self._global_settings)
            sublime.save_settings("LSP.sublime-settings")

    def enable(self, config_name: str) -> None:
        self._set_enabled(config_name, True)

    def disable(self, config_name: str) -> None:
        self._set_enabled(config_name, False)

    def set_listener(self, recipient: Callable) -> None:
        self._listener = recipient

    def is_syntax_supported(self, syntax: str) -> bool:
        if syntax in self._supported_syntaxes_cache:
            return self._supported_syntaxes_cache[syntax]
        scope = syntax2scope(syntax)
        supported = bool(scope and any(config.match_document(scope) for config in self.all))
        self._supported_syntaxes_cache[syntax] = supported
        return supported


_settings_obj = None  # type: Optional[sublime.Settings]
settings = Settings()
client_configs = ClientConfigs()


def load_settings() -> None:
    global _settings_obj
    loaded_settings_obj = sublime.load_settings("LSP.sublime-settings")
    _settings_obj = loaded_settings_obj
    update_settings(settings, loaded_settings_obj)
    client_configs.update(loaded_settings_obj, also_update_configs=False)
    loaded_settings_obj.add_on_change("_on_new_settings", lambda: update_settings(settings, loaded_settings_obj))
    loaded_settings_obj.add_on_change(
        "_on_new_client_settings",
        lambda: client_configs.update(loaded_settings_obj, also_update_configs=True))


def unload_settings() -> None:
    if _settings_obj:
        _settings_obj.clear_on_change("_on_new_settings")
        _settings_obj.clear_on_change("_on_new_client_settings")


def convert_syntaxes_to_selector(d: Union[sublime.Settings, Dict[str, Any]]) -> Optional[str]:
    syntaxes = d.get("syntaxes")
    if isinstance(syntaxes, list) and syntaxes:
        scopes = set()
        for syntax in syntaxes:
            scope = syntax2scope(syntax)
            if scope:
                scopes.add(scope)
        if scopes:
            selector = "|".join(scopes)
            debug('"syntaxes" is deprecated, use "document_selector" instead. The document_selector for', syntaxes,
                  'was deduced to "{}"'.format(selector))
            return selector
    return None


def _has(d: Union[sublime.Settings, Dict[str, Any]], key: str) -> bool:
    if isinstance(d, sublime.Settings):
        return d.has(key)
    else:
        return key in d


def read_language_config(config: Union[sublime.Settings, Dict[str, Any]]) -> LanguageConfig:
    lang_id = config.get("languageId")
    if lang_id is None:
        # "languageId" must exist, just raise a KeyError if it doesn't exist.
        raise KeyError("languageId")
    document_selector = None  # type: Optional[str]
    feature_selector = None  # type: Optional[str]
    if _has(config, "syntaxes"):
        document_selector = convert_syntaxes_to_selector(config)
        feature_selector = document_selector
    if _has(config, "document_selector"):
        # Overwrites potential old assignment to document_selector, which is OK.
        document_selector = config.get("document_selector")
    if _has(config, "feature_selector"):
        # Overwrites potential old assignment to feature_selector, which is OK.
        feature_selector = config.get("feature_selector")
    return LanguageConfig(language_id=lang_id, document_selector=document_selector, feature_selector=feature_selector)


def read_language_configs(client_config: Union[sublime.Settings, Dict[str, Any]]) -> List[LanguageConfig]:
    languages = client_config.get("languages")
    if isinstance(languages, list):
        return list(map(read_language_config, languages))
    if _has(client_config, "languageId"):
        return [read_language_config(client_config)]
    return []


def read_client_config(name: str, d: Dict[str, Any]) -> ClientConfig:
    return ClientConfig(
        name=name,
        binary_args=d.get("command", []),
        languages=read_language_configs(d),
        tcp_port=d.get("tcp_port", None),
        enabled=d.get("enabled", False),
        init_options=d.get("initializationOptions", dict()),
        settings=DottedDict(d.get("settings", None)),
        env=d.get("env", dict()),
        tcp_host=d.get("tcp_host", None),
        tcp_mode=d.get("tcp_mode", None),
        experimental_capabilities=d.get("experimental_capabilities", dict())
    )


def update_client_config(external_config: ClientConfig, user_override_config: Dict[str, Any]) -> ClientConfig:
    user_override_languages = read_language_configs(user_override_config)
    if not user_override_languages:
        user_override_languages = external_config.languages
    user_override_settings = user_override_config.get("settings")
    if isinstance(user_override_settings, dict):
        settings = DottedDict(deepcopy(external_config.settings.get()))
        settings.update(user_override_settings)
    else:
        settings = external_config.settings
    return ClientConfig(
        name=external_config.name,
        binary_args=user_override_config.get("command", external_config.binary_args),
        languages=user_override_languages,
        tcp_port=user_override_config.get("tcp_port", external_config.tcp_port),
        enabled=user_override_config.get("enabled", external_config.enabled),
        init_options=user_override_config.get("init_options", external_config.init_options),
        settings=settings,
        env=user_override_config.get("env", external_config.env),
        tcp_host=user_override_config.get("tcp_host", external_config.tcp_host),
        tcp_mode=user_override_config.get("tcp_mode", external_config.tcp_mode),
        experimental_capabilities=user_override_config.get(
            "experimental_capabilities", external_config.experimental_capabilities)
    )
