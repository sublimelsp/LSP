# Stubs for sublime.py (Python 3.3 API Environment)
from typing import Any, Callable, Dict, Iterator, List, Literal, Optional, Reversible, Sequence, Tuple, Union


HOVER_TEXT = ...  # type: int
"""The mouse is hovered over the text."""
HOVER_GUTTER = ...  # type: int
"""The mouse is hovered over the gutter."""
HOVER_MARGIN = ...  # type: int
"""The mouse is hovered in the white space to the right of a line."""

ENCODED_POSITION = ...  # type: int
"""Indicates that the file name should be searched for a `:row` or `:row:col` suffix."""
TRANSIENT = ...  # type: int
"""Open the file as a preview only: it won't have a tab assigned it until modified."""
FORCE_GROUP = ...  # type: int
"""Don't select the file if it is open in a different group. Instead make a new clone of that file in the desired group."""
SEMI_TRANSIENT = ...  # type: int
"""If a sheet is newly created, it will be set to semi-transient. Semi-transient sheets generally replace other semi-transient sheets. This is used for the side-bar preview. Only valid with `ADD_TO_SELECTION` or `REPLACE_MRU`."""
ADD_TO_SELECTION = ...  # type: int
"""Add the file to the currently selected sheets in the group."""
REPLACE_MRU = ...  # type: int
"""Causes the sheet to replace the most-recently used sheet in the current sheet selection."""
CLEAR_TO_RIGHT = ...  # type: int
"""All currently selected sheets to the right of the most-recently used sheet will be unselected before opening the file. Only valid in combination with `ADD_TO_SELECTION`."""
FORCE_CLONE = ...  # type: int
"""Don't select the file if it is open. Instead make a new clone of that file in the desired group."""

LITERAL = ...  # type: int
"""Whether the find pattern should be matched literally or as a regex."""
IGNORECASE = ...  # type: int
"""Whether case should be considered when matching the find pattern."""
WHOLEWORD = ...  # type: int
"""Whether to only match whole words."""
REVERSE = ...  # type: int
"""Whether to search backwards."""
WRAP = ...  # type: int
"""Whether to wrap around once the end is reached."""

MONOSPACE_FONT = ...  # type: int
"""Use a monospace font."""
KEEP_OPEN_ON_FOCUS_LOST = ...  # type: int
"""Keep the quick panel open if the window loses input focus."""
WANT_EVENT = ...  # type: int
"""Pass a second parameter to the `on_done` callback, a `Event`."""

HTML = ...  # type: int
COOPERATE_WITH_AUTO_COMPLETE = ...  # type: int
"""Causes the popup to display next to the auto complete menu."""
HIDE_ON_MOUSE_MOVE = ...  # type: int
"""Causes the popup to hide when the mouse is moved, clicked or scrolled."""
HIDE_ON_MOUSE_MOVE_AWAY = ...  # type: int
"""Causes the popup to hide when the mouse is moved (unless towards the popup), or when clicked or scrolled."""
KEEP_ON_SELECTION_MODIFIED = ...  # type: int
"""Prevent the popup from hiding when the selection is modified."""
HIDE_ON_CHARACTER_EVENT = ...  # type: int
"""Hide the popup when a character is typed."""

DRAW_EMPTY = ...  # type: int
"""Draw empty regions with a vertical bar. By default, they aren't drawn at all."""
HIDE_ON_MINIMAP = ...  # type: int
"""Don't show the regions on the minimap."""
DRAW_EMPTY_AS_OVERWRITE = ...  # type: int
"""Draw empty regions with a horizontal bar instead of a vertical one."""
PERSISTENT = ...  # type: int
"""Save the regions in the session."""
DRAW_NO_FILL = ...  # type: int
"""Disable filling the regions, leaving only the outline."""
HIDDEN = ...  # type: int
"""Don't draw the regions."""
DRAW_NO_OUTLINE = ...  # type: int
"""Disable drawing the outline of the regions."""
DRAW_SOLID_UNDERLINE = ...  # type: int
"""Draw a solid underline below the regions."""
DRAW_STIPPLED_UNDERLINE = ...  # type: int
"""Draw a stippled underline below the regions."""
DRAW_SQUIGGLY_UNDERLINE = ...  # type: int
"""Draw a squiggly underline below the regions."""
NO_UNDO = ...  # type: int

OP_EQUAL = ...  # type: int
OP_NOT_EQUAL = ...  # type: int
OP_REGEX_MATCH = ...  # type: int
OP_NOT_REGEX_MATCH = ...  # type: int
OP_REGEX_CONTAINS = ...  # type: int
OP_NOT_REGEX_CONTAINS = ...  # type: int
CLASS_WORD_START = ...  # type: int
"""The point is the start of a word."""
CLASS_WORD_END = ...  # type: int
"""The point is the end of a word."""
CLASS_PUNCTUATION_START = ...  # type: int
"""The point is the start of a sequence of punctuation characters."""
CLASS_PUNCTUATION_END = ...  # type: int
"""The point is the end of a sequence of punctuation characters."""
CLASS_SUB_WORD_START = ...  # type: int
"""The point is the start of a sub-word."""
CLASS_SUB_WORD_END = ...  # type: int
"""The point is the end of a sub-word."""
CLASS_LINE_START = ...  # type: int
"""The point is the start of a line."""
CLASS_LINE_END = ...  # type: int
"""The point is the end of a line."""
CLASS_EMPTY_LINE = ...  # type: int
"""The point is an empty line."""

INHIBIT_WORD_COMPLETIONS = ...  # type: int
"""Prevent Sublime Text from showing completions based on the contents of the view."""
INHIBIT_EXPLICIT_COMPLETIONS = ...  # type: int
"""Prevent Sublime Text from showing completions based on `.sublime-completions` files."""
DYNAMIC_COMPLETIONS = ...  # type: int
"""If completions should be re-queried as the user types."""
INHIBIT_REORDER = ...  # type: int
"""Prevent Sublime Text from changing the completion order."""

DIALOG_CANCEL = ...  # type: int
DIALOG_YES = ...  # type: int
DIALOG_NO = ...  # type: int

LAYOUT_INLINE = ...  # type: int
"""The phantom is positioned inline with the text at the beginning of its `Region`."""
LAYOUT_BELOW = ...  # type: int
"""The phantom is positioned below the line, left-aligned with the beginning of its `Region`."""
LAYOUT_BLOCK = ...  # type: int
"""The phantom is positioned below the line, left-aligned with the beginning of the line."""

KIND_ID_AMBIGUOUS = ...  # type: int
KIND_ID_KEYWORD = ...  # type: int
KIND_ID_TYPE = ...  # type: int
KIND_ID_FUNCTION = ...  # type: int
KIND_ID_NAMESPACE = ...  # type: int
KIND_ID_NAVIGATION = ...  # type: int
KIND_ID_MARKUP = ...  # type: int
KIND_ID_VARIABLE = ...  # type: int
KIND_ID_SNIPPET = ...  # type: int

KIND_ID_COLOR_REDISH = ... # type: int
KIND_ID_COLOR_ORANGISH = ... # type: int
KIND_ID_COLOR_YELLOWISH = ... # type: int
KIND_ID_COLOR_GREENISH = ... # type: int
KIND_ID_COLOR_CYANISH = ... # type: int
KIND_ID_COLOR_BLUISH = ... # type: int
KIND_ID_COLOR_PURPLISH = ... # type: int
KIND_ID_COLOR_PINKISH = ... # type: int
KIND_ID_COLOR_DARK = ... # type: int
KIND_ID_COLOR_LIGHT = ... # type: int

KIND_AMBIGUOUS = ...  # type: Tuple[int, str, str]
KIND_KEYWORD = ...  # type: Tuple[int, str, str]
KIND_TYPE = ...  # type: Tuple[int, str, str]
KIND_FUNCTION = ...  # type: Tuple[int, str, str]
KIND_NAMESPACE = ...  # type: Tuple[int, str, str]
KIND_NAVIGATION = ...  # type: Tuple[int, str, str]
KIND_MARKUP = ...  # type: Tuple[int, str, str]
KIND_VARIABLE = ...  # type: Tuple[int, str, str]
KIND_SNIPPET = ...  # type: Tuple[int, str, str]

SYMBOL_SOURCE_ANY = ...  # type: int
"""Use any source - both the index and open files."""
SYMBOL_SOURCE_INDEX = ...  # type: int
"""Use the index created when scanning through files in a project folder."""
SYMBOL_SOURCE_OPEN_FILES = ...  # type: int
"""Use the open files, unsaved or otherwise."""

SYMBOL_TYPE_ANY = ...  # type: int
"""Any symbol type - both definitions and references."""
SYMBOL_TYPE_DEFINITION = ...  # type: int
"""Only definitions."""
SYMBOL_TYPE_REFERENCE = ...  # type: int
"""Only references."""

COMPLETION_FORMAT_TEXT = ...  # type: int
"""Plain text, upon completing the text is inserted verbatim."""
COMPLETION_FORMAT_SNIPPET = ...  # type: int
"""A snippet, with `$` variables."""
COMPLETION_FORMAT_COMMAND = ...  # type: int
"""A command string, in the format returned by `format_command()`."""

COMPLETION_FLAG_KEEP_PREFIX = ...  # type: int


class Settings:
    settings_id = ...  # type: int

    def __init__(self, id: int) -> None:
        ...

    def get(self, key: str, default: Optional[Any] = ...) -> Optional[Any]:
        ...

    def has(self, key: str) -> bool:
        ...

    def set(self, key: str, value: Any) -> None:
        ...

    def erase(self, key: str) -> None:
        ...

    def add_on_change(self, tag: str, callback: Callable[[], None]) -> None:
        ...

    def clear_on_change(self, tag: str) -> None:
        ...


def version() -> str:
    """The version number."""
    ...


def platform() -> Literal["osx", "linux", "windows"]:
    """The platform which the plugin is being run on."""
    ...


def arch() -> Literal["x32", "x64", "arm64"]:
    """The CPU architecture."""
    ...


def channel() -> Literal["dev", "stable"]:
    """The release channel of this build of Sublime Text."""
    ...


def executable_path() -> str:
    """The path to the main Sublime Text executable."""
    ...


def executable_hash() -> Tuple[str, str, str]:
    """A tuple uniquely identifying the installation of Sublime Text."""
    ...


def packages_path() -> str:
    """The path to the "Packages" folder."""
    ...


def installed_packages_path() -> str:
    """The path to the "Installed Packages" folder."""
    ...


def cache_path() -> str:
    """The path where Sublime Text stores cache files."""
    ...


def status_message(msg: str) -> None:
    """Show a message in the status bar."""
    ...


def error_message(msg: str) -> None:
    """Display an error dialog."""
    ...


def message_dialog(msg: str) -> None:
    """Display a message dialog."""
    ...


def ok_cancel_dialog(msg: str, ok_title: str = ...) -> bool:
    ...


def yes_no_cancel_dialog(msg: str, yes_title: str = ..., no_title: str = ...) -> int:
    ...


def run_command(cmd: str, args: Optional[Any] = ...) -> None:
    ...


def get_clipboard(size_limit: int = ...) -> str:
    ...


def set_clipboard(text: str) -> None:
    ...


def log_commands(flag: bool) -> None:
    ...


def log_input(flag: bool) -> None:
    ...


def log_result_regex(flag: bool) -> None:
    ...


def log_indexing(flag: bool) -> None:
    ...


def log_build_systems(flag: bool) -> None:
    ...


def score_selector(scope_name: str, selector: str) -> int:
    ...


def load_resource(name: str) -> str:
    ...


def load_binary_resource(name: str) -> bytes:
    ...


def find_resources(pattern: str) -> Sequence[str]:
    ...


def encode_value(val: Any, pretty: bool = ...) -> str:
    ...


def decode_value(data: str) -> Any:
    ...


def expand_variables(val: Any, variables: dict) -> Any:
    ...


def load_settings(base_name: str) -> Settings:
    ...


def save_settings(base_name: str) -> None:
    ...


def set_timeout(f: Callable[[], Any], timeout_ms: int = ...) -> None:
    ...


def set_timeout_async(f: Callable[[], Any], timeout_ms: int = ...) -> None:
    ...


def active_window() -> 'Window':
    ...


def windows() -> 'Sequence[Window]':
    ...


def get_macro() -> Sequence[dict]:
    ...


def syntax_from_path(syntax_path: str) -> Optional[Syntax]:
    ...


def command_url(cmd: str, args: Optional[dict] = ...) -> str:
    ...


class Syntax:
    path = ...  # type: str
    name = ...  # type: str
    hidden = ...  # type: bool
    scope = ...  # type: str

    def __init__(self, path: str, name: str, hidden: bool, scope: str) -> None:
        ...


class CompletionItem:
    trigger = ...  # type: str
    annotation = ...  # type: str
    completion = ...  # type: str
    completion_format = ...  # type: int
    kind = ...  # type: Tuple[int, str, str]
    details = ...  # type: str
    flags = ...  # type: int

    def __init__(
            self,
            trigger: str,
            annotation: str = "",
            completion: str = "",
            completion_format: int = COMPLETION_FORMAT_TEXT,
            kind: Tuple[int, str, str] = KIND_AMBIGUOUS,
            details: str = "") -> None:
        ...

    @classmethod
    def snippet_completion(
            cls,
            trigger: str,
            snippet: str,
            annotation: str = " ",
            kind: Tuple[int, str, str] = KIND_SNIPPET,
            details: str = "") -> 'CompletionItem':
        ...

    @classmethod
    def command_completion(cls,
                           trigger: str,
                           command: str,
                           args: dict = {},
                           annotation: str = "",
                           kind: Tuple[int, str, str] = KIND_AMBIGUOUS,
                           details: str = ""
                           ) -> 'CompletionItem':
        ...


class CompletionList:
    def set_completions(self, completions: List[CompletionItem], flags: int = 0) -> None:
        ...


class Window:
    window_id = ...  # type: int
    settings_object = ...  # type: Settings
    template_settings_object = ...  # type: Any

    def __init__(self, id: int) -> None:
        ...

    def __eq__(self, other: object) -> bool:
        ...

    def __bool__(self) -> bool:
        ...

    def id(self) -> int:
        ...

    def is_valid(self) -> bool:
        ...

    # def hwnd(self): ...
    def active_sheet(self) -> 'Sheet':
        ...

    def active_view(self) -> 'Optional[View]':
        ...

    def new_html_sheet(self, name: str, contents: str, flags: int = ..., group: int = ...) -> 'Sheet':
        ...

    def run_command(self, cmd: str, args: Optional[Any] = ...) -> None:
        ...

    def new_file(self, flags: int = ..., syntax: str = ...) -> 'View':
        ...

    def open_file(self, fname: str, flags: int = ..., group: int = ...) -> 'View':
        ...

    def find_open_file(self, fname: str, group: int = ...) -> 'Optional[View]':
        ...

    def num_groups(self) -> int:
        ...

    def active_group(self) -> int:
        ...

    def focus_group(self, idx: int) -> None:
        ...

    def focus_sheet(self, sheet: 'Sheet') -> None:
        ...

    def focus_view(self, view: 'View') -> None:
        ...

    def select_sheets(self, sheets: 'List[Sheet]') -> None:
        ...

    def get_sheet_index(self, sheet: 'Sheet') -> Tuple[int, int]:
        ...

    def get_view_index(self, view: 'View') -> Tuple[int, int]:
        ...

    def set_sheet_index(self, sheet: 'Sheet', group: int, idx: int) -> None:
        ...

    def set_view_index(self, view: 'View', group: int, idx: int) -> None:
        ...

    def sheets(self) -> 'List[Sheet]':
        ...

    def selected_sheets(self) -> 'List[Sheet]':
        ...

    def selected_sheets_in_group(self, group: int) -> 'List[Sheet]':
        ...

    def views(self) -> 'List[View]':
        ...

    def active_sheet_in_group(self, group: int) -> 'Sheet':
        ...

    def active_view_in_group(self, group: int) -> 'Optional[View]':
        ...

    def sheets_in_group(self, group: int) -> 'List[Sheet]':
        ...

    def views_in_group(self, group: int) -> 'List[View]':
        ...

    def transient_sheet_in_group(self, group: int) -> 'Sheet':
        ...

    def transient_view_in_group(self, group: int) -> 'View':
        ...

    # def layout(self): ...
    # def get_layout(self): ...
    # def set_layout(self, layout): ...
    def create_output_panel(self, name: str, unlisted: bool = ...) -> 'View':
        ...

    def find_output_panel(self, name: str) -> 'Optional[View]':
        ...

    def destroy_output_panel(self, name: str) -> None:
        ...

    def active_panel(self) -> Optional[str]:
        ...

    def panels(self) -> List[str]:
        ...

    def get_output_panel(self, name: str) -> 'Optional[View]':
        ...

    def show_input_panel(self, caption: str, initial_text: str, on_done: Optional[Callable],
                         on_change: Optional[Callable], on_cancel: Optional[Callable]) -> 'View':
        ...

    def show_quick_panel(self,
                         items: List[Any],
                         on_select: Callable,
                         flags: int = ...,
                         selected_index: int = ...,
                         on_highlight: Optional[Callable] = ...,
                         placeholder: Optional[str] = ...) -> None:
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

    def folders(self) -> List[str]:
        ...

    def project_file_name(self) -> str:
        ...

    def project_data(self) -> Optional[dict]:
        ...

    def set_project_data(self, v: Union[dict, None]) -> None:
        ...

    def settings(self) -> Settings:
        ...

    # def template_settings(self): ...
    def lookup_symbol_in_index(self, sym: str) -> List[str]:
        ...

    def lookup_symbol_in_open_files(self, sym: str) -> List[str]:
        ...

    def extract_variables(self) -> dict:
        ...

    def status_message(self, msg: str) -> None:
        ...


class Edit:
    edit_token = ...  # type: Any

    def __init__(self, token: Any) -> None:
        ...


class Region:
    a = ...  # type: int
    b = ...  # type: int
    xpos = ...  # type: int

    def __init__(self, a: int, b: Optional[int] = ..., xpos: int = ...) -> None:
        ...

    def __len__(self) -> int:
        ...

    def __eq__(self, rhs: object) -> bool:
        ...

    def __lt__(self, rhs: object) -> bool:
        ...

    def empty(self) -> bool:
        ...

    def begin(self) -> int:
        ...

    def end(self) -> int:
        ...

    def size(self) -> int:
        ...

    def contains(self, x: 'Union[Region, int]') -> bool:
        ...

    def cover(self, rhs: 'Region') -> 'Region':
        ...

    def intersection(self, rhs: 'Region') -> 'Region':
        ...

    def intersects(self, rhs: 'Region') -> bool:
        ...

    def to_tuple(self) -> Tuple[int, int]:
        ...


class Selection(Reversible):
    view_id = ...  # type: Any

    def __init__(self, id: Any) -> None:
        ...

    def __reversed__(self) -> Iterator[Region]:
        ...

    def __iter__(self) -> Iterator[Region]:
        ...

    def __len__(self) -> int:
        ...

    def __getitem__(self, index: int) -> Region:
        ...

    def __delitem__(self, index: int) -> None:
        ...

    def __eq__(self, rhs: Any) -> bool:
        ...

    def __lt__(self, rhs: Any) -> bool:
        ...

    def __bool__(self) -> bool:
        ...

    def is_valid(self) -> bool:
        ...

    def clear(self) -> None:
        ...

    def add(self, x: Union[Region, int]) -> None:
        ...

    def add_all(self, regions: Iterator[Union[Region, int]]) -> None:
        ...

    def subtract(self, region: Region) -> None:
        ...

    def contains(self, region: Region) -> bool:
        ...


class Sheet:
    sheet_id = ...  # type: Any

    def __init__(self, id: Any) -> None:
        ...

    def __eq__(self, other: object) -> bool:
        ...

    def id(self) -> int:
        ...

    def window(self) -> Optional[Window]:
        ...

    def group(self) -> int:
        ...

    def view(self) -> 'Optional[View]':
        ...

    def is_semi_transient(self) -> bool:
        ...

    def is_transient(self) -> bool:
        ...


class HtmlSheet(Sheet):
    sheet_id = ...  # type: Any

    def __init__(self, id: Any) -> None:
        ...

    def set_name(self, name: str) -> None:
        ...

    def set_contents(self, contents: str) -> None:
        ...


class ContextStackFrame:
    context_name = ... # type: str
    source_file = ... # type: str
    source_location = ... # type: Tuple[int, int]


class View:
    view_id = ...  # type: Any
    selection = ...  # type: Any
    settings_object = ...  # type: Any

    def __init__(self, id: Any) -> None:
        ...

    def __len__(self) -> int:
        ...

    def __eq__(self, other: object) -> bool:
        ...

    def __bool__(self) -> bool:
        ...

    def sheet(self) -> Sheet:
        ...

    def syntax(self) -> Any:
        ...

    def element(self) -> Optional[str]:
        ...

    def id(self) -> int:
        ...

    def buffer(self) -> "Optional[Buffer]":
        ...

    def buffer_id(self) -> int:
        ...

    def is_valid(self) -> bool:
        ...

    def is_primary(self) -> bool:
        ...

    def window(self) -> Optional[Window]:
        ...

    def file_name(self) -> Optional[str]:
        ...

    def close(self) -> None:
        ...

    def retarget(self, new_fname: str) -> None:
        ...

    def name(self) -> str:
        ...

    def set_name(self, name: str) -> None:
        ...

    def is_loading(self) -> bool:
        ...

    def is_dirty(self) -> bool:
        ...

    def is_read_only(self) -> bool:
        ...

    def set_read_only(self, read_only: bool) -> None:
        ...

    def is_scratch(self) -> bool:
        ...

    def set_scratch(self, scratch: bool) -> None:
        ...

    def encoding(self) -> str:
        ...

    def set_encoding(self, encoding_name: str) -> None:
        ...

    def line_endings(self) -> str:
        ...

    def set_line_endings(self, line_ending_name: str) -> None:
        ...

    def size(self) -> int:
        ...

    # def begin_edit(self, edit_token, cmd, args: Optional[Any] = ...) -> Edit: ...
    # def end_edit(self, edit: Edit) -> None: ...
    def is_in_edit(self) -> bool:
        ...

    def insert(self, edit: Edit, pt: int, text: str) -> None:
        ...

    def erase(self, edit: Edit, r: Region) -> None:
        ...

    def replace(self, edit: Edit, r: Region, text: str) -> None:
        ...

    def change_count(self) -> int:
        ...

    def run_command(self, cmd: str, args: Optional[Any] = ...) -> None:
        ...

    def sel(self) -> Selection:
        ...

    def substr(self, x: Union[Region, int]) -> str:
        ...

    def find(self, pattern: str, start_pt: int, flags: int = ...) -> Optional[Region]:
        ...

    def find_all(self, pattern: str, flags: int = ..., fmt: Optional[Any] = ...,
                 extractions: Optional[Any] = ...) -> 'List[Region]':
        ...

    def settings(self) -> Settings:
        ...

    # def meta_info(self, key, pt: int): ...
    def extract_scope(self, pt: int) -> Region:
        ...

    def scope_name(self, pt: int) -> str:
        ...

    def context_backtrace(self, pt: int) -> Union[List[ContextStackFrame], List[str]]:
        ...

    def match_selector(self, pt: int, selector: str) -> bool:
        ...

    def score_selector(self, pt: int, selector: str) -> int:
        ...

    def find_by_selector(self, selector: str) -> List[Region]:
        ...

    # def indented_region(self, pt: int): ...
    # def indentation_level(self, pt: int): ...
    def has_non_empty_selection_region(self) -> bool:
        ...

    def lines(self, r: Region) -> List[Region]:
        ...

    def split_by_newlines(self, r: Region) -> List[Region]:
        ...

    def line(self, x: Union[Region, int]) -> Region:
        ...

    def full_line(self, x: Union[Region, int]) -> Region:
        ...

    def word(self, x: Union[Region, int]) -> Region:
        ...

    def classify(self, pt: int) -> int:
        ...

    def find_by_class(self, pt: int, forward: bool, classes: int, separators: str = ...) -> int:
        ...

    def expand_by_class(self, x: Union[Region, int], classes: int, separators: str = ...) -> Region:
        ...

    def rowcol(self, tp: int) -> Tuple[int, int]:
        ...

    def rowcol_utf8(self, tp: int) -> Tuple[int, int]:
        ...

    def rowcol_utf16(self, tp: int) -> Tuple[int, int]:
        ...

    def text_point(self, row: int, col: int, *, clamp_column: bool = False) -> int:
        ...

    def text_point_utf8(self, row: int, col_utf8: int, *, clamp_column: bool = False) -> int:
        ...

    def text_point_utf16(self, row: int, col_utf16: int, *, clamp_column: bool = False) -> int:
        ...

    def visible_region(self) -> Region:
        ...

    def show(self, x: Union[Selection, Region, int], show_surrounds: bool = True, keep_to_left: bool = False,
             animate: bool = True) -> None:
        ...

    def show_at_center(self, x: Union[Selection, Region, int], animate: bool = True) -> None:
        ...

    def viewport_position(self) -> Tuple[int, int]:
        ...

    def set_viewport_position(self, xy: Tuple[int, int], animate: bool = ...) -> None:
        ...

    def viewport_extent(self) -> Tuple[int, int]:
        ...

    def layout_extent(self) -> Tuple[int, int]:
        ...

    def text_to_layout(self, tp: int) -> Tuple[int, int]:
        ...

    def layout_to_text(self, xy: Tuple[int, int]) -> int:
        ...

    def window_to_layout(self, xy: Tuple[int, int]) -> Tuple[int, int]:
        ...

    def window_to_text(self, xy: Tuple[int, int]) -> int:
        ...

    def line_height(self) -> float:
        ...

    def em_width(self) -> float:
        ...

    def is_folded(self, sr: Region) -> bool:
        ...

    # def folded_regions(self): ...
    def fold(self, x: Union[Region, List[Region]]) -> bool:
        ...

    def unfold(self, x: Union[Region, List[Region]]) -> List[Region]:
        ...

    def add_regions(self, key: str, regions: List[Region], scope: str = ..., icon: str = ..., flags: int = ...,
                    annotations: List[str] = ..., annotation_color: str = ...,
                    on_navigate: Callable[[str], None] = ..., on_close: Callable[[], None] = ...) -> None:
        ...

    def get_regions(self, key: str) -> List[Region]:
        ...

    def erase_regions(self, key: str) -> None:
        ...

    # def add_phantom(self, key: str, region: Region, content: str, layout, on_navigate: Optional[Any] = ...): ...
    # def erase_phantoms(self, key: str) -> None: ...
    # def erase_phantom_by_id(self, pid) -> None: ...
    # def query_phantom(self, pid): ...
    # def query_phantoms(self, pids): ...
    def assign_syntax(self, syntax_file: str) -> None:
        ...

    def set_syntax_file(self, syntax_file: str) -> None:
        ...

    def symbols(self) -> List[Tuple[Region, str]]:
        ...

    # def get_symbols(self): ...
    # def indexed_symbols(self): ...
    def set_status(self, key: str, value: str) -> None:
        ...

    def get_status(self, key: str) -> str:
        ...

    def erase_status(self, key: str) -> None:
        ...

    # def extract_completions(self, prefix: str, tp: int = ...): ...
    # def find_all_results(self): ...
    # def find_all_results_with_text(self): ...
    def command_history(self, delta: int, modifying_only: bool = ...) -> 'Tuple[str, dict, int]':
        ...

    def overwrite_status(self) -> bool:
        ...

    def set_overwrite_status(self, value: bool) -> None:
        ...

    def show_popup_menu(self, items: List[str], on_select: 'Callable', flags: int = ...) -> None:
        ...

    def show_popup(self,
                   content: str,
                   flags: int = ...,
                   location: int = ...,
                   max_width: int = ...,
                   max_height: int = ...,
                   on_navigate: Optional[Any] = ...,
                   on_hide: Optional[Any] = ...) -> None:
        ...

    def update_popup(self, content: str) -> None:
        ...

    def is_popup_visible(self) -> bool:
        ...

    def hide_popup(self) -> None:
        ...

    def is_auto_complete_visible(self) -> bool:
        ...

    def change_id(self) -> Any:  # opaque handle object
        ...

    def transform_region_from(self, region: Region, change_id: Any) -> Region:
        ...

    def style_for_scope(self, scope: str) -> Dict[str, Any]:
        ...


class Buffer:
    buffer_id = ...  # type: int

    def __init__(self, id: int) -> None:
        ...

    def views(self) -> Optional[List[View]]:
        ...

    def primary_view(self) -> Optional[View]:
        ...


class Phantom:
    region = ...  # type: Region
    content = ...  # type: Any
    layout = ...  # type: Any
    on_navigate = ...  # type: Any
    id = ...  # type: Any

    def __init__(self, region: Region, content: str, layout: int, on_navigate: Optional[Any] = ...) -> None:
        ...

    def __eq__(self, rhs: object) -> bool:
        ...


class PhantomSet:
    view = ...  # type: View
    key = ...  # type: Any
    phantoms = ...  # type: Any

    def __init__(self, view: View, key: str = ...) -> None:
        ...

    def __del__(self) -> None:
        ...

    def update(self, new_phantoms: Sequence[Phantom]) -> None:
        ...


class HistoricPosition:
    pt = ...  # type: int
    row = ...  # type: int
    col = ...  # type: int
    col_utf16 = ...  # type: int
    col_utf8 = ...  # type: int


class TextChange:
    a = ...  # type: HistoricPosition
    b = ...  # type: HistoricPosition
    str = ...  # type: str
    len_utf8 = ...  # type: int
    len_utf16 = ...  # type: int


class QuickPanelItem:
    def __init__(
        self,
        trigger: str,
        details: Union[str, List[str]] = "",
        annotation: str = "",
        kind: Tuple[int, str, str] = KIND_AMBIGUOUS
    ) -> None:
        ...


class ListInputItem:
    value = ...  # type: Any
    kind = ...  # type: Tuple[int, str, str]
    def __init__(
        self,
        text: str,
        value: Any,
        details: Union[str, List[str]] = "",
        annotation: str = "",
        kind: Tuple[int, str, str] = KIND_AMBIGUOUS
    ) -> None:
        ...


class Html:
    def __init__(
        self,
        text: str,
    ) -> None:
        ...
