from .typing import Optional, List, Dict, Any, Iterator, Iterable, Protocol
import plistlib
import re
import sublime


class UnrecognizedExtensionError(Exception):

    def __init__(self, syntax: str) -> None:
        super().__init__("unrecognized extension: {}".format(syntax))
        self.syntax = syntax


def base_scope_from_view(view: Any) -> str:
    return view.scope_name(0).strip().split()[0]


def _read_base_scope_from_syntax_file(syntax: str) -> str:
    if syntax.endswith(".sublime-syntax"):
        match = re.search(r'^scope: (\S+)', sublime.load_resource(syntax), re.MULTILINE)
        return match.group(1) if match else ""
    elif syntax.endswith(".tmLanguage") or syntax.endswith(".hidden-tmLanguage"):
        # TODO: What should this encoding be?
        content = sublime.load_resource(syntax).encode("utf-8")
        # TODO: When on python 3.8, use plistlib.loads instead, and use plistlib.FMT_XML
        data = plistlib.readPlistFromBytes(content)  # type: Dict[str, Any]
        return data.get("scopeName", "")
    else:
        raise UnrecognizedExtensionError(syntax)


_syntax2scope = {}  # type: Dict[str, str]


def base_scope_from_syntax(syntax: str) -> str:
    global _syntax2scope
    base_scope = _syntax2scope.get(syntax, None)  # type: Optional[str]
    if base_scope is None:
        try:
            base_scope = _read_base_scope_from_syntax_file(syntax)
            _syntax2scope[syntax] = base_scope
        except Exception as ex:
            _syntax2scope[syntax] = ""
            raise ex from ex
    return base_scope


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
    def __init__(self, language_id: str, scopes: List[str], syntaxes: Optional[List[str]] = None) -> None:
        self.id = language_id
        self.scopes = scopes
        # TODO: Update all LanguageHandlers

    def __repr__(self) -> str:
        return 'LanguageConfig({}, {})'.format(repr(self.id), repr(self.scopes))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, LanguageConfig):
            return False
        return self.id == other.id and self.scopes == other.scopes

    def score(self, base_scope: str) -> int:
        return max(sublime.score_selector(base_scope, s) for s in self.scopes)

    def supports(self, base_scope: str) -> bool:
        return self.score(base_scope) > 0


class ClientConfig(object):
    def __init__(self,
                 name: str,
                 binary_args: List[str],
                 tcp_port: Optional[int],
                 scopes: List[str] = [],
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
            assert languageId
            assert len(scopes) > 0
            languages = [LanguageConfig(languageId, scopes)]
        self.languages = languages
        self.enabled = enabled
        self.init_options = init_options
        self.settings = settings
        self.env = env

    def __repr__(self) -> str:
        return 'ClientConfig({}, {}, {}, {}, {}, {}, {}, {}, {}, {})'.format(
            repr(self.name),
            repr(self.binary_args),
            repr(self.tcp_port),
            repr([]),
            repr(None),
            repr(self.languages),
            repr(self.enabled),
            repr(self.init_options),
            repr(self.settings),
            repr(self.env))

    def score(self, base_scope: str) -> int:
        return max(language.score(base_scope) for language in self.languages)

    def supports(self, base_scope: str) -> bool:
        return self.score(base_scope) > 0


class ViewLike(Protocol):

    def file_name(self) -> Optional[str]:
        ...

    def scope_name(self, point: int) -> str:
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

    def syntax_configs(self, view: ViewLike, include_disabled: bool = False) -> Iterable[ClientConfig]:
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
