from .typing import Optional, List, Dict, Any, Protocol
import sublime


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
        self.show_references_in_quick_panel = False
        self.disabled_capabilities = []  # type: List[str]
        self.log_debug = True
        self.log_server = True
        self.log_stderr = False
        self.log_payloads = False


class ClientStates(object):
    STARTING = 0
    READY = 1
    STOPPING = 2


class LanguageConfig(object):

    __slots__ = ('id', 'selector')

    def __init__(self, language_id: str, selector: Optional[str] = None) -> None:
        self.id = language_id
        self.selector = selector if selector else "source.{}".format(self.id)

    def score(self, base_scope: str) -> int:
        return sublime.score_selector(base_scope, self.selector)

    def match(self, base_scope: str) -> bool:
        # Every part of a x.y.z scope seems to contribute 8.
        # An empty selector result in a score of 1.
        # A non-matching non-empty selector results in a score of 0.
        # We want to match at least one part of an x.y.z, and we don't want to match on empty selectors.
        return self.score(base_scope) >= 8


class ClientConfig(object):
    def __init__(self,
                 name: str,
                 binary_args: List[str],
                 tcp_port: Optional[int],
                 selector: Optional[str] = None,
                 languageId: Optional[str] = None,
                 languages: List[LanguageConfig] = [],
                 enabled: bool = True,
                 init_options: dict = dict(),
                 settings: dict = dict(),
                 env: dict = dict(),
                 tcp_host: Optional[str] = None,
                 tcp_mode: Optional[str] = None,
                 experimental_capabilities: dict = dict()) -> None:
        self.name = name
        self.binary_args = binary_args
        self.tcp_port = tcp_port
        self.tcp_host = tcp_host
        self.tcp_mode = tcp_mode
        if not languages:
            languages = [LanguageConfig(languageId, selector)] if languageId else []
        self.languages = languages
        self.enabled = enabled
        self.init_options = init_options
        self.settings = settings
        self.env = env
        self.experimental_capabilities = experimental_capabilities

    def supports(self, base_scope: str) -> bool:
        return any(language.match(base_scope) for language in self.languages)


def syntax2scope(syntax: str) -> Optional[str]:
    try:
        return next(filter(lambda d: d['path'] == syntax, sublime.list_syntaxes()))['scope']
    except StopIteration:
        return None


def view2scope(view: sublime.View, point: Optional[int] = None) -> str:
    return view.scope_name(0 if point is None else point).strip().split()[0]


class ViewLike(Protocol):
    def id(self) -> int:
        ...

    def is_valid(self) -> bool:
        ...

    def file_name(self) -> Optional[str]:
        ...

    def change_count(self) -> int:
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
