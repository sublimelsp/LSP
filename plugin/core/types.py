from .typing import Optional, List, Dict, Any, Iterator, Protocol


class Settings(object):

    def __init__(self) -> None:
        self.show_view_status = True
        self.auto_show_diagnostics_panel = 'always'
        self.auto_show_diagnostics_panel_level = 2
        self.show_diagnostics_count_in_view_status = False
        self.show_diagnostics_in_view_status = True
        self.show_diagnostics_severity_level = 2
        self.only_show_lsp_completions = False
        self.diagnostics_highlight_style = "underline"
        self.document_highlight_style = "stippled"
        self.document_highlight_scopes = {
            "unknown": "text",
            "text": "text",
            "read": "markup.inserted",
            "write": "markup.changed"
        }
        self.diagnostics_gutter_marker = "dot"
        self.show_code_actions_bulb = False
        self.show_symbol_action_links = False
        self.complete_all_chars = False
        self.completion_hint_type = "auto"
        self.show_references_in_quick_panel = False
        self.disabled_capabilities = []  # type: List[str]
        self.log_debug = True
        self.log_server = True
        self.log_stderr = False
        self.log_payloads = False


class LanguageConfig(object):
    def __init__(self, language_id: str, scopes: List[str], syntaxes: List[str]) -> None:
        self.id = language_id
        self.scopes = scopes
        self.syntaxes = syntaxes


class ClientConfig(object):
    def __init__(self,
                 name: str,
                 binary_args: List[str],
                 tcp_port: Optional[int],
                 scopes: List[str] = [],
                 syntaxes: List[str] = [],
                 languageId: Optional[str] = None,
                 languages: List[LanguageConfig] = [],
                 enabled: bool = True,
                 init_options: dict = dict(),
                 settings: dict = dict(),
                 env: dict = dict(),
                 tcp_host: Optional[str] = None,
                 tcp_mode: Optional[str] = None) -> None:
        self.name = name
        self.binary_args = binary_args
        self.tcp_port = tcp_port
        self.tcp_host = tcp_host
        self.tcp_mode = tcp_mode
        if not languages:
            languages = [LanguageConfig(languageId, scopes, syntaxes)] if languageId else []
        self.languages = languages
        self.enabled = enabled
        self.init_options = init_options
        self.settings = settings
        self.env = env


def syntax_language(config: ClientConfig, syntax: str) -> Optional[LanguageConfig]:
    for language in config.languages:
        for lang_syntax in language.syntaxes:
            if lang_syntax == syntax:
                return language
    return None


def config_supports_syntax(config: ClientConfig, syntax: str) -> bool:
    return bool(syntax_language(config, syntax))


class ViewLike(Protocol):
    def file_name(self) -> Optional[str]:
        ...

    def window(self) -> Optional[Any]:  # WindowLike
        ...

    def buffer_id(self) -> int:
        ...

    def substr(self, region: Any) -> str:
        ...

    def settings(self) -> Any:  # SettingsLike
        ...

    def size(self) -> int:
        ...

    def set_status(self, key: str, status: str) -> None:
        ...

    def sel(self) -> Any:
        ...

    def score_selector(self, region: Any, scope: str) -> int:
        ...

    def run_command(self, command_name: str, command_args: Dict[str, Any]) -> None:
        ...


class WindowLike(Protocol):
    def id(self) -> int:
        ...

    def is_valid(self) -> bool:
        ...

    def folders(self) -> List[str]:
        ...

    def find_open_file(self, path: str) -> Optional[ViewLike]:
        ...

    def num_groups(self) -> int:
        ...

    def active_group(self) -> int:
        ...

    def active_view_in_group(self, group: int) -> ViewLike:
        ...

    def project_data(self) -> Optional[dict]:
        ...

    def project_file_name(self) -> Optional[str]:
        ...

    def active_view(self) -> Optional[ViewLike]:
        ...

    def status_message(self, msg: str) -> None:
        ...

    def views(self) -> List[ViewLike]:
        ...

    def run_command(self, command_name: str, command_args: Dict[str, Any]) -> None:
        ...


class ConfigRegistry(Protocol):
    # todo: calls config_for_scope immediately.
    all = []  # type: List[ClientConfig]

    def is_supported(self, view: ViewLike) -> bool:
        ...

    def scope_configs(self, view: ViewLike, point: Optional[int] = None) -> Iterator[ClientConfig]:
        ...

    def syntax_configs(self, view: ViewLike, include_disabled: bool = False) -> List[ClientConfig]:
        ...

    def syntax_supported(self, view: ViewLike) -> bool:
        ...

    def syntax_config_languages(self, view: ViewLike) -> Dict[str, LanguageConfig]:
        ...

    def update(self) -> None:
        ...

    def disable_temporarily(self, config_name: str) -> None:
        ...


class GlobalConfigs(Protocol):
    def for_window(self, window: WindowLike) -> ConfigRegistry:
        ...
