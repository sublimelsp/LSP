from .workspace import get_first_workspace_from_window, absolute_project_base_path
from .url import uri_to_filename
from .logging import debug
import os

try:
    from typing_extensions import Protocol
    from typing import Optional, List, Callable, Dict, Any, Iterator, Iterable, Tuple
    assert Optional and List and Callable and Dict and Any and Iterator and Iterable and Tuple
except ImportError:
    pass
    Protocol = object  # type: ignore


class Settings(object):

    def __init__(self) -> None:
        self.show_status_messages = True
        self.show_view_status = True
        self.auto_show_diagnostics_panel = True
        self.auto_show_diagnostics_panel_level = 3
        self.show_diagnostics_phantoms = False
        self.show_diagnostics_count_in_view_status = False
        self.show_diagnostics_in_view_status = True
        self.show_diagnostics_severity_level = 3
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
        self.prefer_label_over_filter_text = False
        self.show_references_in_quick_panel = False
        self.quick_panel_monospace_font = False
        self.disabled_capabilities = []  # type: List[str]
        self.log_debug = True
        self.log_server = True
        self.log_stderr = False
        self.log_payloads = False


class ClientStates(object):
    STARTING = 0
    READY = 1
    STOPPING = 2


def syntax_language(config: 'ClientConfig', syntax: str) -> 'Optional[LanguageConfig]':
    for language in config.languages:
        for lang_syntax in language.syntaxes:
            if lang_syntax == syntax:
                return language
    return None


def config_supports_syntax(config: 'ClientConfig', syntax: str) -> bool:
    return bool(syntax_language(config, syntax))


class ConfigWorkingDir:

    first_folder = "first_folder"  # Reverts to sublime_cache_path on failure
    project_folder = "project_folder"  # Reverts to first_folder on failure
    sublime_cache_path = "sublime_cache_path"  # Must not fail :-)


class LanguageConfig(object):
    def __init__(self, language_id: str, scopes: 'List[str]', syntaxes: 'List[str]') -> None:
        self.id = language_id
        self.scopes = scopes
        self.syntaxes = syntaxes


class ClientConfig(object):
    def __init__(self,
                 name: str,
                 binary_args: 'List[str]',
                 tcp_port: 'Optional[int]',
                 scopes: 'List[str]' = [],
                 syntaxes: 'List[str]' = [],
                 languageId: 'Optional[str]' = None,
                 languages: 'List[LanguageConfig]' = [],
                 enabled: bool = True,
                 init_options: dict = dict(),
                 settings: dict = dict(),
                 env: dict = dict(),
                 tcp_host: 'Optional[str]' = None,
                 tcp_mode: 'Optional[str]' = None,
                 working_dir: str = ConfigWorkingDir.first_folder) -> None:
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
        self.working_dir = working_dir

    def resolve_working_dir(self, window: 'WindowLike') -> str:
        if self.working_dir == ConfigWorkingDir.first_folder:
            return self.__first_folder(window)
        elif self.working_dir == ConfigWorkingDir.project_folder:
            return self.__project_folder(window)
        elif self.working_dir == ConfigWorkingDir.sublime_cache_path:
            return self.__sublime_cache_path(window)
        else:
            debug('unknown working_dir, reverting to "{}"'.format(ConfigWorkingDir.first_folder))
            return self.__first_folder(window)

    def __first_folder(self, window: 'WindowLike') -> str:
        try:
            return uri_to_filename(get_first_workspace_from_window(window).uri)
        except Exception as ex:
            debug(str(ex))
        return self.__sublime_cache_path(window)

    def __project_folder(self, window: 'WindowLike') -> str:
        try:
            return absolute_project_base_path(window)
        except Exception as ex:
            debug(str(ex))
        return self.__first_folder(window)

    def __sublime_cache_path(self, window: 'WindowLike') -> str:
        tempdir = ''
        try:
            import sublime
            tempdir = sublime.cache_path()
        except ImportError:
            import tempfile
            tempdir = tempfile.gettempdir()
        tempdir = os.path.join(tempdir, 'LSP', self.name)
        os.makedirs(tempdir, exist_ok=True)
        return tempdir


class ViewLike(Protocol):

    def id(self) -> int:
        ...

    def file_name(self) -> 'Optional[str]':
        ...

    def window(self) -> 'Optional[Any]':  # WindowLike
        ...

    def buffer_id(self) -> int:
        ...

    def substr(self, region: 'Any') -> str:
        ...

    def settings(self) -> 'Any':  # SettingsLike
        ...

    def size(self) -> int:
        ...

    def set_status(self, key: str, status: str) -> None:
        ...

    def sel(self) -> 'Any':
        ...

    def score_selector(self, region: 'Any', scope: str) -> int:
        ...

    def assign_syntax(self, syntax: str) -> None:
        ...

    def set_read_only(self, val: bool) -> None:
        ...

    def run_command(self, command_name: str, command_args: 'Optional[Dict[str, Any]]' = None) -> None:
        ...

    def find_all(self, selector: str) -> 'Iterable[Tuple[int, int]]':
        ...

    def add_regions(self, key: str, regions: 'Iterable[Any]', scope: str = "", icon: str = "", flags: int = 0) -> None:
        ...


class WindowLike(Protocol):
    def id(self) -> int:
        ...

    def active_view(self) -> 'Optional[Any]':
        ...

    def run_command(self, cmd: str, args: 'Optional[Dict[str, Any]]') -> None:
        ...

    def new_file(self, flags: int, syntax: str) -> 'Any':
        ...

    def open_file(self, fname: str, flags: int, group: int) -> 'Any':
        ...

    def is_valid(self) -> bool:
        ...

    def folders(self) -> 'List[str]':
        ...

    # should return Optional[ViewLike], but creates conflict when a real sublime.View is presented
    def find_open_file(self, path: str) -> 'Optional[Any]':
        ...

    def num_groups(self) -> int:
        ...

    def active_group(self) -> int:
        ...

    def focus_group(self, idx: int) -> None:
        ...

    def active_view_in_group(self, group: int) -> 'Any':  # should be ViewLike, but conflicts in configurations.py
        ...

    # def layout(self):
    #     ...

    # def get_layout(self):
    #     ...

    # def set_layout(self, layout):
    #     ...

    # should return ViewLike, but creates conflict in panels.py
    def create_output_panel(self, name: str, unlisted: bool = False) -> 'Any':
        ...

    # should return Optional[ViewLike], but creates conflict when a real sublime.View is presented
    def find_output_panel(self, name: str) -> 'Optional[Any]':
        ...

    def destroy_output_panel(self, name: str) -> None:
        ...

    def active_panel(self) -> 'Optional[str]':
        ...

    def panels(self) -> 'List[str]':
        ...

    def views(self) -> 'List[Any]':
        ...

    def get_output_panel(self, name: str) -> 'Optional[Any]':
        ...

    def show_input_panel(self, caption: str, initial_text: str, on_done: 'Callable', on_change: 'Any',
                         on_cancel: 'Any') -> 'Any':
        ...

    def show_quick_panel(self, items: 'List[Any]', on_select: 'Callable', flags: int,
                         selected_index: int, on_highlight: 'Optional[Any]') -> None:
        ...

    def is_sidebar_visible(self) -> bool:
        ...

    def set_sidebar_visible(self, flag: bool) -> None:
        ...

    def is_minimap_visible(self) -> bool:
        ...

    def set_minimap_visible(self, flag: bool) -> None:
        ...

    def is_status_bar_visible(self) -> bool:
        ...

    def set_status_bar_visible(self, flag: bool) -> None:
        ...

    def get_tabs_visible(self) -> bool:
        ...

    def set_tabs_visible(self, flag: bool) -> None:
        ...

    def is_menu_visible(self) -> bool:
        ...

    def set_menu_visible(self, flag: bool) -> None:
        ...

    def project_file_name(self) -> 'Optional[str]':
        ...

    def project_data(self) -> 'Optional[dict]':
        ...

    def set_project_data(self, v: dict) -> None:
        ...

    def lookup_symbol_in_index(self, sym: str) -> 'List[str]':
        ...

    def lookup_symbol_in_open_files(self, sym: str) -> 'List[str]':
        ...

    def extract_variables(self) -> dict:
        ...

    def status_message(self, msg: str) -> None:
        ...


class ConfigRegistry(Protocol):
    # todo: calls config_for_scope immediately.
    all = []  # type: List[ClientConfig]

    def is_supported(self, view: ViewLike) -> bool:
        ...

    def scope_configs(self, view: ViewLike, point: 'Optional[int]' = None) -> 'Iterator[ClientConfig]':
        ...

    def syntax_configs(self, view: ViewLike) -> 'List[ClientConfig]':
        ...

    def syntax_supported(self, view: ViewLike) -> bool:
        ...

    def syntax_config_languages(self, view: ViewLike) -> 'Dict[str, LanguageConfig]':
        ...

    def update(self, configs: 'List[ClientConfig]') -> None:
        ...

    def disable(self, config_name: str) -> None:
        ...


class GlobalConfigs(Protocol):
    def for_window(self, window: WindowLike) -> ConfigRegistry:
        ...
