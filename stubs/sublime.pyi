# Stubs for sublime.py (Python 3.3 API Environment)
from typing import Any, Callable, Dict, Iterable, Iterator, List, Literal, Optional, Reversible, Sequence, Tuple
from typing_extensions import deprecated


HOVER_TEXT: Literal[1]
"""The mouse is hovered over the text."""
HOVER_GUTTER: Literal[2]
"""The mouse is hovered over the gutter."""
HOVER_MARGIN: Literal[3]
"""The mouse is hovered in the white space to the right of a line."""

ENCODED_POSITION: Literal[1]
"""Indicates that the file name should be searched for a `:row` or `:row:col` suffix."""
TRANSIENT: Literal[4]
"""Open the file as a preview only: it won't have a tab assigned it until modified."""
FORCE_GROUP: Literal[8]
"""
Don't select the file if it is open in a different group. Instead make a new clone of that file in the desired group.
"""
SEMI_TRANSIENT: Literal[16]
"""
If a sheet is newly created, it will be set to semi-transient. Semi-transient sheets generally replace other
semi-transient sheets. This is used for the side-bar preview. Only valid with `ADD_TO_SELECTION` or `REPLACE_MRU`.
"""
ADD_TO_SELECTION: Literal[32]
"""Add the file to the currently selected sheets in the group."""
REPLACE_MRU: Literal[64]
"""Causes the sheet to replace the most-recently used sheet in the current sheet selection."""
CLEAR_TO_RIGHT: Literal[128]
"""
All currently selected sheets to the right of the most-recently used sheet will be unselected before opening the file.
Only valid in combination with `ADD_TO_SELECTION`.
"""
FORCE_CLONE: Literal[256]
"""Don't select the file if it is open. Instead make a new clone of that file in the desired group."""

LITERAL: Literal[1]
"""Whether the find pattern should be matched literally or as a regex."""
IGNORECASE: Literal[2]
"""Whether case should be considered when matching the find pattern."""
WHOLEWORD: Literal[4]
"""Whether to only match whole words."""
REVERSE: Literal[8]
"""Whether to search backwards."""
WRAP: Literal[16]
"""Whether to wrap around once the end is reached."""

MONOSPACE_FONT: Literal[1]
"""Use a monospace font."""
KEEP_OPEN_ON_FOCUS_LOST: Literal[2]
"""Keep the quick panel open if the window loses input focus."""
WANT_EVENT: Literal[4]
"""Pass a second parameter to the `on_done` callback, a `Event`."""

HTML: Literal[1]
COOPERATE_WITH_AUTO_COMPLETE: Literal[2]
"""Causes the popup to display next to the auto complete menu."""
HIDE_ON_MOUSE_MOVE: Literal[4]
"""Causes the popup to hide when the mouse is moved, clicked or scrolled."""
HIDE_ON_MOUSE_MOVE_AWAY: Literal[8]
"""Causes the popup to hide when the mouse is moved (unless towards the popup), or when clicked or scrolled."""
KEEP_ON_SELECTION_MODIFIED: Literal[16]
"""Prevent the popup from hiding when the selection is modified."""
HIDE_ON_CHARACTER_EVENT: Literal[32]
"""Hide the popup when a character is typed."""

DRAW_EMPTY: Literal[1]
"""Draw empty regions with a vertical bar. By default, they aren't drawn at all."""
HIDE_ON_MINIMAP: Literal[2]
"""Don't show the regions on the minimap."""
DRAW_EMPTY_AS_OVERWRITE: Literal[4]
"""Draw empty regions with a horizontal bar instead of a vertical one."""
PERSISTENT: Literal[16]
"""Save the regions in the session."""
DRAW_NO_FILL: Literal[32]
"""Disable filling the regions, leaving only the outline."""
HIDDEN: Literal[128]
"""Don't draw the regions."""
DRAW_NO_OUTLINE: Literal[256]
"""Disable drawing the outline of the regions."""
DRAW_SOLID_UNDERLINE: Literal[512]
"""Draw a solid underline below the regions."""
DRAW_STIPPLED_UNDERLINE: Literal[1024]
"""Draw a stippled underline below the regions."""
DRAW_SQUIGGLY_UNDERLINE: Literal[2048]
"""Draw a squiggly underline below the regions."""
NO_UNDO: Literal[8192]

OP_EQUAL: Literal[0]
OP_NOT_EQUAL: Literal[1]
OP_REGEX_MATCH: Literal[2]
OP_NOT_REGEX_MATCH: Literal[3]
OP_REGEX_CONTAINS: Literal[4]
OP_NOT_REGEX_CONTAINS: Literal[5]
CLASS_WORD_START: Literal[1]
"""The point is the start of a word."""
CLASS_WORD_END: Literal[2]
"""The point is the end of a word."""
CLASS_PUNCTUATION_START: Literal[4]
"""The point is the start of a sequence of punctuation characters."""
CLASS_PUNCTUATION_END: Literal[8]
"""The point is the end of a sequence of punctuation characters."""
CLASS_SUB_WORD_START: Literal[16]
"""The point is the start of a sub-word."""
CLASS_SUB_WORD_END: Literal[32]
"""The point is the end of a sub-word."""
CLASS_LINE_START: Literal[64]
"""The point is the start of a line."""
CLASS_LINE_END: Literal[128]
"""The point is the end of a line."""
CLASS_EMPTY_LINE: Literal[256]
"""The point is an empty line."""

INHIBIT_WORD_COMPLETIONS: Literal[8]
"""Prevent Sublime Text from showing completions based on the contents of the view."""
INHIBIT_EXPLICIT_COMPLETIONS: Literal[16]
"""Prevent Sublime Text from showing completions based on `.sublime-completions` files."""
DYNAMIC_COMPLETIONS: Literal[32]
"""If completions should be re-queried as the user types."""
INHIBIT_REORDER: Literal[128]
"""Prevent Sublime Text from changing the completion order."""

DIALOG_CANCEL: Literal[0]
DIALOG_YES: Literal[1]
DIALOG_NO: Literal[2]

LAYOUT_INLINE: Literal[0]
"""The phantom is positioned inline with the text at the beginning of its `Region`."""
LAYOUT_BELOW: Literal[1]
"""The phantom is positioned below the line, left-aligned with the beginning of its `Region`."""
LAYOUT_BLOCK: Literal[2]
"""The phantom is positioned below the line, left-aligned with the beginning of the line."""

KIND_ID_AMBIGUOUS: Literal[0]
KIND_ID_KEYWORD: Literal[1]
KIND_ID_TYPE: Literal[2]
KIND_ID_FUNCTION: Literal[3]
KIND_ID_NAMESPACE: Literal[4]
KIND_ID_NAVIGATION: Literal[5]
KIND_ID_MARKUP: Literal[6]
KIND_ID_VARIABLE: Literal[7]
KIND_ID_SNIPPET: Literal[8]

KIND_ID_COLOR_REDISH: Literal[9]
KIND_ID_COLOR_ORANGISH: Literal[10]
KIND_ID_COLOR_YELLOWISH: Literal[11]
KIND_ID_COLOR_GREENISH: Literal[12]
KIND_ID_COLOR_CYANISH: Literal[13]
KIND_ID_COLOR_BLUISH: Literal[14]
KIND_ID_COLOR_PURPLISH: Literal[15]
KIND_ID_COLOR_PINKISH: Literal[16]
KIND_ID_COLOR_DARK: Literal[17]
KIND_ID_COLOR_LIGHT: Literal[18]

KIND_AMBIGUOUS: Tuple[int, str, str]
KIND_KEYWORD: Tuple[int, str, str]
KIND_TYPE: Tuple[int, str, str]
KIND_FUNCTION: Tuple[int, str, str]
KIND_NAMESPACE: Tuple[int, str, str]
KIND_NAVIGATION: Tuple[int, str, str]
KIND_MARKUP: Tuple[int, str, str]
KIND_VARIABLE: Tuple[int, str, str]
KIND_SNIPPET: Tuple[int, str, str]

SYMBOL_SOURCE_ANY: Literal[0]
"""Use any source - both the index and open files."""
SYMBOL_SOURCE_INDEX: Literal[1]
"""Use the index created when scanning through files in a project folder."""
SYMBOL_SOURCE_OPEN_FILES: Literal[2]
"""Use the open files, unsaved or otherwise."""

SYMBOL_TYPE_ANY: Literal[0]
"""Any symbol type - both definitions and references."""
SYMBOL_TYPE_DEFINITION: Literal[1]
"""Only definitions."""
SYMBOL_TYPE_REFERENCE: Literal[2]
"""Only references."""

COMPLETION_FORMAT_TEXT: Literal[0]
"""Plain text, upon completing the text is inserted verbatim."""
COMPLETION_FORMAT_SNIPPET: Literal[1]
"""A snippet, with `$` variables."""
COMPLETION_FORMAT_COMMAND: Literal[2]
"""A command string, in the format returned by `format_command()`."""

COMPLETION_FLAG_KEEP_PREFIX: Literal[1]


def version() -> str:
    """
    The version number.
    """
    ...


def platform() -> Literal["osx", "linux", "windows"]:
    """
    The platform which the plugin is being run on.
    """
    ...


def arch() -> Literal["x32", "x64", "arm64"]:
    """
    The CPU architecture.
    """
    ...


def channel() -> Literal["dev", "stable"]:
    """
    The release channel of this build of Sublime Text.
    """
    ...


def executable_path() -> str:
    """
    The path to the main Sublime Text executable.
    """
    ...


def executable_hash() -> Tuple[str, str, str]:
    """
    A tuple uniquely identifying the installation of Sublime Text.
    """
    ...


def packages_path() -> str:
    """
    The path to the "Packages" folder.
    """
    ...


def installed_packages_path() -> str:
    """
    The path to the "Installed Packages" folder.
    """
    ...


def cache_path() -> str:
    """
    The path where Sublime Text stores cache files.
    """
    ...


def status_message(msg: str) -> None:
    """
    Show a message in the status bar.
    """
    ...


def error_message(msg: str) -> None:
    """
    Display an error dialog.
    """
    ...


def message_dialog(msg: str) -> None:
    """
    Display a message dialog.
    """
    ...


def ok_cancel_dialog(msg: str, ok_title: str = ..., title: str = ...) -> bool:
    """
    Show a popup dialog with an "ok" and "cancel" button.

    - `msg` - The message to show in the dialog.
    - `ok_title` - Optional replacement string for the "ok" button.
    - `title` - Optional title for the dialog. Note Linux and macOS do not have a title in their dialog.

    Returns `True` if the user presses the `ok` button, `False` otherwise.
    """
    ...


def yes_no_cancel_dialog(msg: str, yes_title: str = ..., no_title: str = ..., title: str = ...) -> int:
    """
    Show a popup dialog with a "yes", "no" and "cancel" button.

    - `msg` - The message to show in the dialog.
    - `yes_title` - Optional replacement string for the "yes" button.
    - `no_title` - Optional replacement string for the "no" button.
    - `title` - Optional title for the dialog. Note Linux and macOS do not have a title in their dialog.

    Returns `DIALOG_YES`, `DIALOG_NO` or `DIALOG_CANCEL`.
    """
    ...


def open_dialog(
    callback: Callable[[str | List[str] | None], None],
    file_types: List[Tuple[str, List[str]]] = ...,
    directory: str | None = ...,
    multi_select: bool = ...,
    allow_folders: bool = ...
) -> None:
    """
    Show the open file dialog.

    - `callback` - Called with selected path(s) or `None` once the dialog is closed.
    - `file_types` - A list of allowed file types, consisting of a description and a list of allowed extensions.
    - `directory` - The directory the dialog should start in. Will use the virtual working directory if not provided.
    - `multi_select` - Whether to allow selecting multiple files. When `True` the callback will be called with a list.
    - `allow_folders` - Whether to also allow selecting folders. Only works on macOS. If you only want to select folders
        use `select_folder_dialog`.
    """
    ...


def save_dialog(
    callback: Callable[[str | None], None],
    file_types: List[Tuple[str, List[str]]] = ...,
    directory: str | None = ...,
    name: str | None = ...,
    extension: str | None = ...,
) -> None:
    """
    Show the save file dialog.

    - `callback` - Called with selected path or `None` once open dialog is closed.
    - `file_types` - A list of allowed file types, consisting of a description and a list of allowed extensions.
    - `directory` - The directory the dialog should start in. Will use the virtual working directory if not provided.
    - `name` - The default name of the file in the save dialog.
    - `extension` - The default extension used in the save dialog.
    """
    ...


def select_folder_dialog(
    callback: Callable[[str | List[str] | None], None],
    directory: str | None = ...,
    multi_select: bool = ...,
) -> None:
    """
    Show the select folder dialog.

    - `callback` - Called with selected path(s) or `None` once open dialog is closed.
    - `directory` - The directory the dialog should start in. Will use the virtual working directory if not provided.
    - `multi_select` - Whether to allow selecting multiple folders. When `True` the callback will be called with a list.
    """
    ...


def choose_font_dialog(
    callback: Callable[[Dict[str, Any] | None], None],
    default: Dict[str, Any] | None = ...
) -> None:
    """
    Show a dialog for selecting a font.

    - `callback` - Called with the font options, matching the format used in settings
        (eg. `{ "font_face": "monospace" }`). May be called more than once, or will be called with `None` if the dialog
        is cancelled.
    - `default` - The default values to select/return. Same format as the argument passed to `callback`.
    """
    ...


def run_command(cmd: str, args: Dict[str, Any] | None = ...) -> None:
    """
    Runs the named `ApplicationCommand` with the (optional) given `args`.
    """
    ...


def format_command(cmd: str, args: Dict[str, Any] | None = ...) -> str:
    """
    Creates a "command string" from a str cmd name, and an optional dict of args. This is used when constructing a
    command-based `CompletionItem`.
    """
    ...


def html_format_command(cmd: str, args: Dict[str, Any] | None = ...) -> str:
    """
    Creates an escaped "command string" for usage in HTML popups and sheets.
    """
    ...


def command_url(cmd: str, args: Dict[str, Any] | None = ...) -> str:
    """
    Creates a `subl:` protocol URL for executing a command in a minihtml link.
    """
    ...


def get_clipboard_async(callback: Callable[[str], None], size_limit: int = ...) -> None:
    """
    Calls `callback` with the contents of the clipboard. For performance reasons if the size of the clipboard content is
    bigger than `size_limit`, an empty string will be returned.
    """
    ...


@deprecated("Use get_clipboard_async() when possible")
def get_clipboard(size_limit: int = ...) -> str:
    """
    Returns the content of the clipboard. For performance reasons if the size of the clipboard content is bigger than
    size_limit, an empty string will be returned.
    """
    ...


def set_clipboard(text: str) -> None:
    """
    Sets the contents of the clipboard.
    """
    ...


def log_commands(flag: bool | None = ...) -> None:
    """
    Controls command logging. If enabled, all commands run from key bindings and the menu will be logged to the console.

    - `flag` - Whether to log. Passing `None` toggles logging.
    """
    ...


def get_log_commands() -> bool:
    """
    Returns whether command logging is enabled.
    """
    ...


def log_input(flag: bool | None = ...) -> None:
    """
    Control whether all key presses will be logged to the console. Use this to find the names of certain keys on the
    keyboard.

    - `flag` - Whether to log. Passing `None` toggles logging.
    """
    ...


def get_log_input() -> bool:
    """
    Returns whether input logging is enabled.
    """
    ...


def log_fps(flag: bool | None = ...) -> None:
    """
    Control whether rendering timings like frames per second get logged.

    - `flag` - Whether to log. Passing `None` toggles logging.
    """
    ...


def get_log_fps() -> bool:
    """
    Returns whether fps logging is enabled.
    """
    ...


def log_result_regex(flag: bool | None = ...) -> None:
    """
    Control whether result regex logging is enabled. Use this to debug `"file_regex"` and `"line_regex"` in build
    systems.

    - `flag` - Whether to log. Passing `None` toggles logging.
    """
    ...


def get_log_result_regex() -> bool:
    """
    Returns whether result regex logging is enabled.
    """
    ...


def log_indexing(flag: bool | None = ...) -> None:
    """
    Control whether indexing logs are printed to the console.

    - `flag` - Whether to log. Passing `None` toggles logging.
    """
    ...


def get_log_indexing() -> bool:
    """
    Returns whether indexing logging is enabled.
    """
    ...


def log_build_systems(flag: bool | None = ...) -> None:
    """
    Control whether build system logs are printed to the console.

    - `flag` - Whether to log. Passing `None` toggles logging.
    """
    ...


def get_log_build_systems() -> bool:
    """
    Returns whether build system logging is enabled.
    """
    ...


def log_control_tree(flag: bool | None = ...) -> None:
    """
    Control whether control tree logging is enabled. When enabled clicking with Ctrl+Alt will log the control tree under
    the mouse to the console.

    - `flag` - Whether to log. Passing `None` toggles logging.
    """
    ...


def get_log_control_tree() -> bool:
    """
    Returns whether control tree logging is enabled.
    """
    ...


def ui_info() -> Dict[str, Any]:
    """
    Information about the user interface including top-level keys `system`, `theme` and `color_scheme`.
    """
    ...


def score_selector(scope_name: str, selector: str) -> int:
    """
    Match the `selector` against the given `scope_name`, returning a score for how well they match.

    A score of `0` means no match, above `0` means a match. Different selectors may be compared against the same scope:
    a higher score means the selector is a better match for the scope.
    """
    ...


def load_resource(name: str) -> str:
    """
    Loads the given resource. The name should be in the format "Packages/Default/Main.sublime-menu".

    Raises `FileNotFoundError` if resource is not found.
    """
    ...


def load_binary_resource(name: str) -> bytes:
    """
    Loads the given binary resource. The name should be in the format "Packages/Default/Main.sublime-menu".

    Raises `FileNotFoundError` if resource is not found.
    """
    ...


def find_resources(pattern: str) -> Sequence[str]:
    """Finds resources whose file name matches the given glob pattern."""
    ...


def encode_value(val: Any, pretty: bool = ..., update_text: str = ...) -> str:
    """
    Encode a JSON compatible `Value` into a string representation.

    - `pretty` - Whether the result should include newlines and be indented.
    - `update_text` - Incrementally update the value encoded in this text. Best effort is made to preserve the contents
        of `update_text` - comments, indentation, etc. This is the same algorithm used to change settings values.
        Providing this makes `pretty` have no effect.
    """
    ...


def decode_value(data: str) -> Any:
    """
    Decode a JSON string into an object. Note that comments and trailing commas are allowed.

    Raises `ValueError` if the string is not valid JSON.
    """
    ...


def expand_variables(val: Any, variables: Dict[str, str]) -> Any:
    """
    Expands any variables in `val` using the variables defined in the dictionary `variables`. `val` may also be a list
    or dict, in which case the structure will be recursively expanded. Strings should use snippet syntax, for example:

    ```python
    expand_variables("Hello, ${name}", {"name": "Foo"})
    ```
    """
    ...


def load_settings(base_name: str) -> Settings:
    """
    Loads the named settings. The name should include a file name and extension, but not a path. The packages will be
    searched for files matching the base_name, and the results will be collated into the settings object.

    Subsequent calls to `load_settings` with the base_name will return the same object, and not load the settings from
    disk again.
    """
    ...


def save_settings(base_name: str) -> None:
    """
    Flush any in-memory changes to the named settings object to disk.
    """
    ...


def set_timeout(f: Callable[[], Any], timeout_ms: int = ...) -> None:
    """
    Schedules a function to be called in the future. Sublime Text will block while the function is running.
    """
    ...


def set_timeout_async(f: Callable[[], Any], timeout_ms: int = ...) -> None:
    """
    Schedules a function to be called in the future. The function will be called in a worker thread, and Sublime Text
    will not block while the function is running.
    """
    ...


def active_window() -> Window:
    """
    The most recently used `Window`.
    """
    ...


def windows() -> List[Window]:
    """
    A list of all the open windows.
    """
    ...


def get_macro() -> List[Dict[str, Any]]:
    """
    A list of the commands and args that compromise the currently recorded macro. Each dict will contain the keys
    `"command"` and `"args"`.
    """
    ...


def project_history() -> List[str]:
    """
    A list of most recently opened workspaces. Sublime-project files with the same name are listed in place of
    sublime-workspace files.
    """
    ...


def folder_history() -> List[str]:
    """
    A list of recent folders added to sublime projects.
    """
    ...


class Window:
    window_id: int
    settings_object: Settings
    template_settings_object: Settings

    def __init__(self, id: int) -> None:
        ...

    def __eq__(self, other: object) -> bool:
        ...

    def __bool__(self) -> bool:
        ...

    def id(self) -> int:
        """
        A number that uniquely identifies this window.
        """
        ...

    def is_valid(self) -> bool:
        """
        Check whether this window is still valid. Will return `False` for a closed window, for example.
        """
        ...

    def hwnd(self):
        """
        A platform specific window handle. Windows only.
        """
        ...

    def active_sheet(self) -> Sheet | None:
        """
        The currently focused `Sheet`.
        """
        ...

    def active_view(self) -> View | None:
        """
        The currently edited `View`.
        """
        ...

    def new_html_sheet(self, name: str, contents: str, flags: int = ..., group: int = ...) -> Sheet:
        """
        Construct a sheet with HTML contents rendered using minihtml.

        - `name` - The name of the sheet to show in the tab.
        - `contents` - The HTML contents of the sheet.
        - `flags` - Only `TRANSIENT` and `ADD_TO_SELECTION` are allowed.
        - `group` - The group to add the sheet to. `-1` for the active group.
        """
        ...

    def run_command(self, cmd: str, args: Dict[str, Any] | None = ...) -> None:
        """
        Run the named `WindowCommand` with the (optional) given args. This method is able to run any sort of command,
        dispatching the command via input focus.
        """
        ...

    def new_file(self, flags: int = ..., syntax: str = ...) -> View:
        """
        Create a new empty file.

        - `flags` - Either `0`, `TRANSIENT` or `ADD_TO_SELECTION`.
        - `syntax` - The name of the syntax to apply to the file.

        Returns the `View` for the file.
        """
        ...

    def open_file(self, fname: str, flags: int = ..., group: int = ...) -> View:
        """
        Open the named file. If the file is already opened, it will be brought to the front. Note that as file loading
        is asynchronous, operations on the returned view won't be possible until its `is_loading()` method returns
        `False`.

        - `fname` - The path to the file to open.
        - `flags`
        - `group` - The group to add the sheet to. `-1` for the active group.
        """
        ...

    def find_open_file(self, fname: str, group: int = ...) -> View | None:
        """
        Find a opened file by file name.

        - `fname` - The path to the file to open.
        - `group` - The group in which to search for the file. `-1` for any group.

        Returns the `View` to the file or `None` if the file isn't open.
        """
        ...

    def file_history(self) -> List[str]:
        """
        Get the list of previously opened files. This is the same list as File > Open Recent.
        """
        ...

    def num_groups(self) -> int:
        """
        The number of view groups in the window.
        """
        ...

    def active_group(self) -> int:
        """
        The index of the currently selected group.
        """
        ...

    def focus_group(self, idx: int) -> None:
        """
        Focus the specified group, making it active.
        """
        ...

    def focus_sheet(self, sheet: Sheet) -> None:
        """
        Switches to the given `Sheet`.
        """
        ...

    def focus_view(self, view: View) -> None:
        """
        Switches to the given `View`.
        """
        ...

    def select_sheets(self, sheets: List[Sheet]) -> None:
        """
        Change the selected sheets for the entire window.
        """
        ...

    def bring_to_front(self) -> None:
        """
        Bring the window in front of any other windows.
        """
        ...

    def get_sheet_index(self, sheet: Sheet) -> Tuple[int, int]:
        """
        The a tuple of the group and index within the group of the given `Sheet`.
        """
        ...

    def get_view_index(self, view: View) -> Tuple[int, int]:
        """
        The a tuple of the group and index within the group of the given `View`.
        """
        ...

    def set_sheet_index(self, sheet: Sheet, group: int, idx: int) -> None:
        """
        Move the given `Sheet` to the given `group` at the given `index`.
        """
        ...

    def set_view_index(self, view: View, group: int, idx: int) -> None:
        """
        Move the given `View` to the given `group` at the given `index`.
        """
        ...

    def move_sheets_to_group(
        self,
        sheets: List[Sheet],
        group: int,
        insertion_idx: int = ...,
        select: bool = ...
    ) -> None:
        """
        Moves all provided sheets to specified group at insertion index provided. If an index is not provided defaults
        to last index of the destination group.

        - `sheets` - The sheets to move.
        - `group` - The index of the group to move the sheets to.
        - `insertion_idx` - The point inside the group at which to insert the sheets.
        - `select` - Whether the sheets should be selected after moving them.
        """
        ...

    def sheets(self) -> List[Sheet]:
        """
        All open sheets in the window.
        """
        ...

    def views(self, *, include_transient: bool = ...) -> List[View]:
        """
        All open sheets in the window.

        - `include_transient` - Whether the transient sheet should be included.
        """
        ...

    def selected_sheets(self) -> List[Sheet]:
        """
        All selected sheets in the window's currently selected group.
        """
        ...

    def selected_sheets_in_group(self, group: int) -> List[Sheet]:
        """
        All selected sheets in the specified group.
        """
        ...

    def active_sheet_in_group(self, group: int) -> Sheet | None:
        """
        The currently focused `Sheet` in the given group.
        """
        ...

    def active_view_in_group(self, group: int) -> View | None:
        """
        The currently focused `View` in the given group.
        """
        ...

    def sheets_in_group(self, group: int) -> List[Sheet]:
        """
        A list of all sheets in the specified group.
        """
        ...

    def views_in_group(self, group: int) -> List[View]:
        """
        A list of all views in the specified group.
        """
        ...

    def num_sheets_in_group(self, group: int) -> int:
        """
        The number of sheets in the specified group.
        """
        ...

    def num_views_in_group(self, group: int) -> int:
        """
        The number of views in the specified group.
        """
        ...

    def transient_sheet_in_group(self, group: int) -> Sheet | None:
        """
        The transient sheet in the specified group.
        """
        ...

    def transient_view_in_group(self, group: int) -> View | None:
        """
        The transient view in the specified group.
        """
        ...

    def promote_sheet(self, sheet: Sheet) -> None:
        """
        Promote the 'Sheet' parameter if semi-transient or transient.
        """
        ...

    def layout(self):
        """
        Get the group layout of the window.
        """
        ...

    @deprecated("Use layout() instead")
    def get_layout(self):
        ...

    def set_layout(self, layout: Dict[str, Any]) -> None:
        """
        Set the group layout of the window.
        """
        ...

    def create_output_panel(self, name: str, unlisted: bool = ...) -> View:
        """
        Find the view associated with the named output panel, creating it if required. The output panel can be shown by
        running the `show_panel` window command, with the `panel` argument set to the name with an `"output."` prefix.

        The optional `unlisted` parameter is a boolean to control if the output panel should be listed in the panel
        switcher.
        """
        ...

    def find_output_panel(self, name: str) -> View | None:
        """
        The `View` associated with the named output panel, or `None` if the output panel does not exist.
        """
        ...

    def destroy_output_panel(self, name: str) -> None:
        """
        Destroy the named output panel, hiding it if currently open.
        """
        ...

    def active_panel(self) -> str | None:
        """
        Returns the name of the currently open panel, or None if no panel is open. Will return built-in panel names
        (e.g. `"console"`, `"find"`, etc.) in addition to output panels.
        """
        ...

    def panels(self) -> List[str]:
        """
        Returns a list of the names of all panels that have not been marked as unlisted. Includes certain built-in
        panels in addition to output panels.
        """
        ...

    @deprecated("Use create_output_panel(...) instead")
    def get_output_panel(self, name: str) -> View | None:
        ...

    def show_input_panel(
        self,
        caption: str,
        initial_text: str,
        on_done: Callable[[str], None] | None,
        on_change: Callable[[str], None] | None,
        on_cancel: Callable[[], None] | None
    ) -> View:
        """
        Shows the input panel, to collect a line of input from the user.

        - `caption` - The label to put next to the input widget.
        - `initial_text` - The initial text inside the input widget.
        - `on_done` - Called with the final input when the user presses Enter.
        - `on_change` - Called with the input when it's changed.
        - `on_cancel` - Called when the user cancels input using Esc.

        Returns the `View` used for the input widget.
        """
        ...

    def show_quick_panel(
        self,
        items: List[Any],
        on_select: Callable[..., None],
        flags: int = ...,
        selected_index: int = ...,
        on_highlight: Callable[..., None] = ...,
        placeholder: str | None = ...
    ) -> None:
        """
        Show a quick panel to select an item in a list. on_select will be called once, with the index of the selected
        item. If the quick panel was cancelled, `on_select` will be called with an argument of `-1`.

        - `items` - May be either a list of strings, a list of lists of strings where the first item is the trigger
            and all subsequent strings are details shown below, or a `QuickPanelItem`.
        - `on_select` - Called with the selected item's index when the quick panel is completed. If the panel was
            cancelled this is called with `-1`. A second `Event` argument may be passed when the `WANT_EVENT` flag is
            present.
        - `flags` - Flags controlling behavior.
        - `selected_index` - The initially selected item. `-1` for no selection.
        - `on_highlight` - Called every time the highlighted item in the quick panel is changed.
        - `placeholder` - Text displayed in the filter input field before any query is typed.
        """
        ...

    def is_sidebar_visible(self) -> bool:
        """
        Whether the sidebar is visible.
        """
        ...

    def set_sidebar_visible(self, flag: bool, animate: bool = ...) -> None:
        """
        Hides or shows the sidebar.
        """
        ...

    def is_minimap_visible(self) -> bool:
        """
        Whether the minimap is visible.
        """
        ...

    def set_minimap_visible(self, flag: bool) -> None:
        """
        Hides or shows the minimap.
        """
        ...

    def is_status_bar_visible(self) -> bool:
        """
        Whether the status bar is visible.
        """
        ...

    def set_status_bar_visible(self, flag: bool) -> None:
        """
        Hides or shows the status bar.
        """
        ...

    def get_tabs_visible(self) -> bool:
        """
        Whether the tabs are visible.
        """
        ...

    def set_tabs_visible(self, flag: bool) -> None:
        """
        Hides or shows the tabs.
        """
        ...

    def is_menu_visible(self) -> bool:
        """
        Whether the menu is visible.
        """
        ...

    def set_menu_visible(self, flag: bool) -> None:
        """
        Hides or shows the menu.
        """
        ...

    def folders(self) -> List[str]:
        """
        A list of the currently open folders in this `Window`.
        """
        ...

    def project_file_name(self) -> str | None:
        """
        The name of the currently opened project file, if any.
        """
        ...

    def project_data(self) -> bool | str | int | float | List[Any] | Dict[str, Any] | None:
        """
        The project data associated with the current window. The data is in the same format as the contents of a
        `.sublime-project` file.
        """
        ...

    def set_project_data(self, v: bool | str | int | float | List[Any] | Dict[str, Any] | None) -> None:
        """
        Updates the project data associated with the current window. If the window is associated with a
        `.sublime-project` file, the project file will be updated on disk, otherwise the window will store the data
        internally.
        """
        ...

    def workspace_file_name(self) -> str | None:
        """
        The name of the currently opened workspace file, if any.
        """
        ...

    def settings(self) -> Settings:
        """
        The `Settings` object for this `Window`. Any changes to this settings object will be specific to this window.
        """
        ...

    def template_settings(self):
        """
        Per-window settings that are persisted in the session, and duplicated into new windows.
        """
        ...

    def symbol_locations(
        self,
        sym: str,
        source: int = ...,
        type: int = ...,
        kind_id: int = ...,
        kind_letter: str = ...
    ) -> List[SymbolLocation]:
        """
        Find all locations where the symbol `sym` is located.

        - `sym` - The name of the symbol.
        - `source` - Sources which should be searched for the symbol.
        - `type` - The type of symbol to find.
        - `kind_id` - The kind ID of the symbol.
        - `kind_letter` - The letter representing the kind of the symbol.

        Returns the found symbol locations.
        """
        ...

    @deprecated("Use symbol_locations() instead")
    def lookup_symbol_in_index(self, sym: str) -> List[SymbolLocation]:
        """
        All locations where the symbol is defined across files in the current project.
        """
        ...

    @deprecated("Use symbol_locations() instead")
    def lookup_symbol_in_open_files(self, sym: str) -> List[SymbolLocation]:
        """
        All locations where the symbol is defined across open files.
        """
        ...

    @deprecated("Use symbol_locations() instead")
    def lookup_references_in_index(self, symbol: str) -> List[SymbolLocation]:
        """
        All locations where the symbol is referenced across files in the current project.
        """
        ...

    @deprecated("Use symbol_locations() instead")
    def lookup_references_in_open_files(self, symbol: str) -> List[SymbolLocation]:
        """
        All locations where the symbol is referenced across open files.
        """
        ...

    def extract_variables(self) -> Dict[str, str]:
        """
        Get the `dict` of contextual keys of the window.

        May contain:

        * `"packages"`
        * `"platform"`
        * `"file"`
        * `"file_path"`
        * `"file_name"`
        * `"file_base_name"`
        * `"file_extension"`
        * `"folder"`
        * `"project"`
        * `"project_path"`
        * `"project_name"`
        * `"project_base_name"`
        * `"project_extension"`

        This `dict` is suitable for use with `expand_variables()`.
        """
        ...

    def status_message(self, msg: str) -> None:
        """
        Show a message in the status bar.
        """
        ...


class Edit:
    """
    A grouping of buffer modifications.

    `Edit` objects are passed to `TextCommand`s, and can not be created by the user. Using an invalid `Edit` object, or
    an `Edit` object from a different `View`, will cause the functions that require them to fail.
    """
    edit_token: int

    def __init__(self, token: int) -> None:
        ...


class Region:
    """
    A singular selection region. This region has a order - `b` may be before or at `a`.

    Also commonly used to represent an area of the text buffer, where ordering and `xpos` are generally ignored.
    """
    a: int
    """The first end of the region."""
    b: int
    """The second end of the region. In a selection this is the location of the caret. May be less than `a`."""
    xpos: float
    """
    In a selection this is the target horizontal position of the region. This affects behavior when pressing the up or
    down keys. Use `-1` if undefined.
    """

    def __init__(self, a: int, b: int | None = ..., xpos: float = ...) -> None:
        ...

    def __len__(self) -> int:
        """The size of the region."""
        ...

    def __eq__(self, rhs: object) -> bool:
        """Whether the two regions are identical. Ignores `xpos`."""
        ...

    def __lt__(self, rhs: object) -> bool:
        """Whether this region starts before the rhs. The end of the region is used to resolve ties."""
        ...

    def to_tuple(self) -> Tuple[int, int]:
        """
        Returns a tuple of this region (excluding xpos).

        Use this to uniquely identify a region in a set or similar. Regions
        can't be used for that directly as they may be mutated.
        """
        ...

    def empty(self) -> bool:
        """Whether the region is empty, ie. `a == b`."""
        ...

    def begin(self) -> int:
        """The smaller of `a` and `b`."""
        ...

    def end(self) -> int:
        """The larger of `a` and `b`."""
        ...

    def size(self) -> int:
        """Equivalent to `__len__`."""
        ...

    def contains(self, x: Region | int) -> bool:
        ...

    def cover(self, rhs: Region) -> Region:
        """A `Region` spanning both regions."""
        ...

    def intersection(self, rhs: Region) -> Region:
        """A `Region` covered by both regions."""
        ...

    def intersects(self, rhs: Region) -> bool:
        """Whether the provided region intersects this region."""
        ...


class HistoricPosition:
    """
    Provides a snapshot of the row and column info for a `Point`, before changes were made to a `View`. This is
    primarily useful for replaying changes to a document.
    """
    pt: int
    """The offset from the beginning of the `View`."""
    row: int
    """The row the `pt` was in when the `HistoricPosition` was recorded."""
    col: int
    """The column the `py` was in when the `HistoricPosition` was recorded, in Unicode characters."""
    col_utf16: int
    """The value of `col`, but in UTF-16 code units."""
    col_utf8: int
    """The value of `col`, but in UTF-8 code units."""


class TextChange:
    """
    Represents a change that occurred to the text of a `View`. This is primarily useful for replaying changes to a
    document.
    """
    a: HistoricPosition
    """The beginning `HistoricPosition` of the region that was modified."""
    b: HistoricPosition
    """The ending `HistoricPosition` of the region that was modified."""
    len_utf16: int
    """The length of the old contents, in UTF-16 code units."""
    len_utf8: int
    """The length of the old contents, in UTF-8 code units."""
    str: str
    """A string of the new contents of the region specified by `a` and `b`."""

    def __init__(self, pa: HistoricPosition, pb: HistoricPosition, len_utf16: int, len_utf8: int, s: str) -> None:
        ...


class Selection(Reversible):
    """
    Maintains a set of sorted non-overlapping Regions. A selection may be empty.

    This is primarily used to represent the textual selection.
    """
    view_id: int

    def __init__(self, id: int) -> None:
        ...

    def __reversed__(self) -> Iterator[Region]:
        ...

    def __iter__(self) -> Iterator[Region]:
        ...

    def __len__(self) -> int:
        """
        The number of regions in the selection.
        """
        ...

    def __getitem__(self, index: int) -> Region:
        """
        The region at the given `index`.
        """
        ...

    def __delitem__(self, index: int) -> None:
        """
        Delete the region at the given `index`.
        """
        ...

    def __eq__(self, rhs: Selection | None) -> bool:
        """
        Whether the selections are identical.
        """
        ...

    def __lt__(self, rhs: Selection | None) -> bool:
        ...

    def __bool__(self) -> bool:
        """
        The selection is `True` when not empty.
        """
        ...

    def is_valid(self) -> bool:
        """
        Whether this selection is for a valid view.
        """
        ...

    def clear(self) -> None:
        """
        Remove all regions from the selection.
        """
        ...

    def add(self, x: Region | int) -> None:
        """
        Add a `Region` or point to the selection. It will be merged with the existing regions if intersecting.
        """
        ...

    def add_all(self, regions: Iterable[Region | int]) -> None:
        """
        Add all the regions from the given iterable.
        """
        ...

    def subtract(self, region: Region) -> None:
        """
        Subtract a region from the selection, such that the whole region is no longer contained within the selection.
        """
        ...

    def contains(self, region: Region) -> bool:
        """
        Whether the provided region is contained within the selection.
        """
        ...


class Sheet:
    """
    Represents a content container, i.e. a tab, within a window. Sheets may contain a `View`, or an image preview.
    """
    sheet_id: int

    def __init__(self, id: int) -> None:
        ...

    def __eq__(self, other: object) -> bool:
        ...

    def id(self) -> int:
        """A number that uniquely identifies this sheet."""
        ...

    def window(self) -> Window | None:
        """The `Window` containing this sheet. May be `None` if the sheet has been closed."""
        ...

    def view(self) -> View | None:
        """The `View` contained within the sheet if any."""
        ...

    def file_name(self) -> str | None:
        """The full name of the file associated with the sheet, or `None` if it doesn't exist on disk."""
        ...

    def is_semi_transient(self) -> bool:
        """Whether this sheet is semi-transient."""
        ...

    def is_transient(self) -> bool:
        """
        Whether this sheet is exclusively transient.

        Note that a sheet may be both open as a regular file and be transient. In this case `is_transient` will still
        return `False`.
        """
        ...

    def is_selected(self) -> bool:
        """Whether this sheet is currently selected."""
        ...

    def group(self) -> int | None:
        """The (layout) group that the sheet is contained within."""
        ...

    def close(self, on_close: Callable[[bool], None] = ...) -> None:
        """Closes the sheet."""
        ...


class TextSheet(Sheet):
    """
    Specialization for sheets containing editable text, ie. a `View`.
    """
    def set_name(self, name: str) -> None:
        """Set the name displayed in the tab. Only affects unsaved files."""
        ...


class ImageSheet(Sheet):
    """
    Specialization for sheets containing an image.
    """
    ...


class HtmlSheet(Sheet):
    """
    Specialization for sheets containing HTML.
    """
    def set_name(self, name: str) -> None:
        """Set the name displayed in the tab."""
        ...

    def set_contents(self, contents: str) -> None:
        """Set the HTML content of the sheet."""
        ...


class ContextStackFrame:
    """
    Represents a single stack frame in the syntax highlighting.
    """
    context_name: str
    """The name of the context."""
    source_file: str
    """The name of the file the context is defined in."""
    source_location: Tuple[int, int]
    """
    The location of the context inside the source file as a pair of row and column. Maybe be `(-1, -1)` if the location
    is unclear, like in tmLanguage based syntaxes.
    """


class View:
    """
    Represents a view into a text `Buffer`.

    Note that multiple views may refer to the same `Buffer`, but they have their own unique selection and geometry. A
    list of these may be gotten using `View.clones()` or `Buffer.views()`.
    """
    view_id: int
    selection: Selection
    settings_object: Settings | None

    def __init__(self, id: int) -> None:
        ...

    def __len__(self) -> int:
        ...

    def __eq__(self, other: object) -> bool:
        ...

    def __bool__(self) -> bool:
        ...

    def id(self) -> int:
        """
        A number that uniquely identifies this view.
        """
        ...

    def buffer_id(self) -> int:
        """
        A number that uniquely identifies this view's `Buffer`.
        """
        ...

    def buffer(self) -> Buffer:
        """
        The `Buffer` for which this is a view.
        """
        ...

    def sheet_id(self) -> int:
        """
        The ID of the `Sheet` for this `View`, or `0` if not part of any sheet.
        """
        ...

    def sheet(self) -> Sheet | None:
        """
        The `Sheet` for this view, if displayed in a sheet.
        """
        ...

    def element(self) -> str | None:
        """
        Returns `None` for normal views that are part of a `Sheet`. For views that comprise part of the UI a string is
        returned from the following list:

        * `"console:input"` - The console input.
        * `"goto_anything:input"` - The input for the Goto Anything.
        * `"command_palette:input"` - The input for the Command Palette.
        * `"find:input"` - The input for the Find panel.
        * `"incremental_find:input"` - The input for the Incremental Find panel.
        * `"replace:input:find"` - The Find input for the Replace panel.
        * `"replace:input:replace"` - The Replace input for the Replace panel.
        * `"find_in_files:input:find"` - The Find input for the Find in Files panel.
        * `"find_in_files:input:location"` - The Where input for the Find in Files panel.
        * `"find_in_files:input:replace"` - The Replace input for the Find in Files panel.
        * `"find_in_files:output"` - The output panel for Find in Files (buffer or output panel).
        * `"input:input"` - The input for the Input panel.
        * `"exec:output"` - The output for the exec command.
        * `"output:output"` - A general output panel.

        The console output, indexer status output and license input controls are not accessible via the API.
        """
        ...

    def is_valid(self) -> bool:
        """
        Check whether this view is still valid. Will return `False` for a closed view, for example.
        """
        ...

    def is_primary(self) -> bool:
        """
        Whether view is the primary view into a `Buffer`. Will only be `False` if the user has opened multiple views
        into a file.
        """
        ...

    def window(self) -> Window | None:
        """
        A reference to the window containing the view, if any.
        """
        ...

    def clones(self) -> List[View]:
        """
        All the other views into the same `Buffer`.
        """
        ...

    def file_name(self) -> str | None:
        """
        The full name of the file associated with the sheet, or `None` if it doesn't exist on disk.
        """
        ...

    def close(self, on_close: Callable[[bool], None] = ...) -> None:
        """
        Closes the view.
        """
        ...

    def retarget(self, new_fname: str) -> None:
        """
        Change the file path the buffer will save to.
        """
        ...

    def name(self) -> str:
        """
        The name assigned to the buffer, if any.
        """
        ...

    def set_name(self, name: str) -> None:
        """
        Assign a name to the buffer. Displayed as in the tab for unsaved files.
        """
        ...

    def reset_reference_document(self) -> None:
        """
        Clears the state of the incremental diff for the view.
        """
        ...

    def set_reference_document(self, reference: str) -> None:
        """
        Uses the string reference to calculate the initial diff for the incremental diff.
        """
        ...

    def is_loading(self) -> bool:
        """
        Whether the buffer is still loading from disk, and not ready for use.
        """
        ...

    def is_dirty(self) -> bool:
        """
        Whether there are any unsaved modifications to the buffer.
        """
        ...

    def is_read_only(self) -> bool:
        """
        Whether the buffer may not be modified.
        """
        ...

    def set_read_only(self, read_only: bool) -> None:
        """
        Set the read only property on the buffer.
        """
        ...

    def is_scratch(self) -> bool:
        """
        Whether the buffer is a scratch buffer. See `set_scratch()`.
        """
        ...

    def set_scratch(self, scratch: bool) -> None:
        """
        Sets the scratch property on the buffer. When a modified scratch buffer is closed, it will be closed without
        prompting to save. Scratch buffers never report as being dirty.
        """
        ...

    def encoding(self) -> str:
        """
        The encoding currently associated with the buffer.
        """
        ...

    def set_encoding(self, encoding_name: str) -> None:
        """
        Applies a new encoding to the file. This will be used when the file is saved.
        """
        ...

    def line_endings(self) -> str:
        """
        The encoding currently associated with the file.
        """
        ...

    def set_line_endings(self, line_ending_name: str) -> None:
        """
        Sets the line endings that will be applied when next saving.
        """
        ...

    def size(self) -> int:
        """
        The number of character in the file.
        """
        ...

    # def begin_edit(self, edit_token: int, cmd: str, args: Dict[str, Any] | None = ...) -> Edit:  # undocumented
    #     ...

    # def end_edit(self, edit: Edit) -> None:  # undocumented
    #     ...

    # def is_in_edit(self) -> bool:  # undocumented
    #     ...

    def insert(self, edit: Edit, pt: int, text: str) -> None:
        """
        Insert the given string into the buffer.

        - `edit` - An `Edit` object provided by a `TextCommand`.
        - `point` - The text point in the view where to insert.
        - `text` - The text to insert.

        Returns the actual number of characters inserted. This may differ from the provided text due to tab translation.

        Raises `ValueError`  if the `Edit` object is in an invalid state, ie. outside of a `TextCommand`.
        """
        ...

    def erase(self, edit: Edit, r: Region) -> None:
        """
        Erases the contents of the provided `Region` from the buffer.
        """
        ...

    def replace(self, edit: Edit, r: Region, text: str) -> None:
        """
        Replaces the contents of the `Region` in the buffer with the provided string.
        """
        ...

    def change_count(self) -> int:
        """
        The current change count.

        Each time the buffer is modified, the change count is incremented. The change count can be used to determine if
        the buffer has changed since the last it was inspected.
        """
        ...

    def change_id(self) -> Tuple[int, int, int]:
        """
        Get a 3-element tuple that can be passed to `transform_region_from()` to obtain a region equivalent to a region
        of the view in the past. This is primarily useful for plugins providing text modification that must operate in
        an asynchronous fashion and must be able to handle the view contents changing between the request and response.
        """
        ...

    def transform_region_from(self, r: Region, when: Tuple[int, int, int]) -> Region:
        """
        Transforms a region from a previous point in time to an equivalent region in the current state of the `View`.
        `when` must have been obtained from `change_id()` at the point in time the region is from.
        """
        ...

    def run_command(self, cmd: str, args: Dict[str, Any] | None = ...) -> None:
        """
        Run the named `TextCommand` with the (optional) given `args`.
        """
        ...

    def sel(self) -> Selection:
        """
        The views `Selection`.
        """
        ...

    def substr(self, x: Region | int) -> str:
        """
        The string at the point or within the `Region` provided.
        """
        ...

    def find(self, pattern: str, start_pt: int, flags: int = ...) -> Region:
        """
        The first `Region` matching the provided pattern.

        - `pattern` - The regex or literal pattern to search by.
        - `start_pt` - The point to start searching from.
        - `flags` - Controls various behaviors of find.
        """
        ...

    def find_all(
        self,
        pattern: str,
        flags: int = ...,
        fmt: str | None = ...,
        extractions: List[str] | None = ...
    ) -> List[Region]:
        """
        All (non-overlapping) regions matching the pattern.

        - `pattern` - The regex or literal pattern to search by.
        - `flags` - Controls various behaviors of find.
        - `fmt` - When not `None` all matches in the `extractions` list will be formatted with the provided format
            string.
        - `extractions` - An optionally provided list to place the contents of the find results into.
        """
        ...

    def settings(self) -> Settings:
        """
        The view's `Settings` object. Any changes to it will be private to this view.
        """
        ...

    def meta_info(self, key: str, pt: int) -> bool | str | int | float | List[Any] | Dict[str, Any] | None:
        """
        Look up the preference `key` for the scope at the provided point `pt` from all matching `.tmPreferences` files.

        Examples of keys are `TM_COMMENT_START` and `showInSymbolList`.
        """
        ...

    def extract_tokens_with_scopes(self, r: Region) -> List[Tuple[Region, str]]:
        """
        A list of pairs containing the `Region` and the scope of each token.

        - `region` - The region from which to extract tokens and scopes.
        """
        ...

    def extract_scope(self, pt: int) -> Region:
        """
        The extent of the syntax scope name assigned to the character at the given point `pt`, narrower syntax scope
        names included.
        """
        ...

    def expand_to_scope(self, pt: int, selector: str) -> Region | None:
        """
        Expand by the provided scope selector from the `Point`.

        - `pt` - The point from which to expand.
        - `selector` - The scope selector to match.

        Returns the matched `Region`, if any.
        """
        ...

    def scope_name(self, pt: int) -> str:
        """
        The syntax scope name assigned to the character at the given point.
        """
        ...

    def context_backtrace(self, pt: int) -> List[ContextStackFrame]:
        """
        Get a backtrace of `ContextStackFrame`s at the provided point `pt`.

        Note this function is particularly slow.
        """
        ...

    def match_selector(self, pt: int, selector: str) -> bool:
        """
        Whether the provided scope selector matches the point `pt`.
        """
        ...

    def score_selector(self, pt: int, selector: str) -> int:
        """
        Equivalent to
        ```python
        sublime.score_selector(view.scope_name(pt), selector)
        ```
        """
        ...

    def find_by_selector(self, selector: str) -> List[Region]:
        """
        Find all regions in the file matching the given selector.
        """
        ...

    def style(self):
        """
        The global style settings for the view. All colors are normalized to the six character hex form with a leading
        hash, e.g. `#ff0000`.
        """
        ...

    def style_for_scope(self, scope: str) -> Dict[str, Any]:
        """
        Accepts a string scope name and returns a `dict` of style information including the keys:

        * `"foreground"`
        * `"background"` (only if set and different from global background)
        * `"bold"`
        * `"italic"`
        * `"glow"`
        * `"underline"`
        * `"stippled_underline"`
        * `"squiggly_underline"`
        * `"source_line"`
        * `"source_column"`
        * `"source_file"`

        The foreground and background colors are normalized to the six character hex form with a leading hash, e.g.
        `#ff0000`.
        """
        ...

    # def indented_region(self, pt: int) -> Region:  # undocumented
    #     ...

    # def indentation_level(self, pt: int) -> int:  # undocumented
    #     ...

    def has_non_empty_selection_region(self) -> bool:  # undocumented
        ...

    def lines(self, r: Region) -> List[Region]:
        """
        A list of lines (in sorted order) intersecting the provided `Region`.
        """
        ...

    def split_by_newlines(self, r: Region) -> List[Region]:
        """
        Splits the region up such that each `Region` returned exists on exactly one line.
        """
        ...

    def line(self, x: Region | int) -> Region:
        """
        The line that contains the point or an expanded `Region` to the beginning/end of lines, excluding the newline
        character.
        """
        ...

    def full_line(self, x: Region | int) -> Region:
        """
        The line that contains the point or an expanded `Region` to the beginning/end of lines, including the newline
        character.
        """
        ...

    def word(self, x: Region | int) -> Region:
        """
        The word that contains the provided point. If a `Region` is provided it's beginning/end are expanded to word
        boundaries.
        """
        ...

    def classify(self, pt: int) -> int:
        """
        Classify the provided point.
        """
        ...

    def find_by_class(
        self,
        pt: int,
        forward: bool,
        classes: int,
        separators: str = ...,
        sub_word_separators: str = ...
    ) -> int:
        """
        Find the next location that matches the provided classification.

        - `pt` - The point to start searching from.
        - `forward` - Whether to search forward or backwards.
        - `classes` - The classification to search for.
        - `separators` - The word separators to use when classifying.
        - `sub_word_separators` - The sub-word separators to use when classifying.
        """
        ...

    def expand_by_class(
        self,
        x: Region | int,
        classes: int,
        separators: str = ...,
        sub_word_separators: str = ...
    ) -> Region:
        """
        Expand the provided point or `Region` to the left and right until each side lands on a location that matches the
        provided classification.

        - `classes` - The classification to search by.
        - `separators` - The word separators to use when classifying.
        - `sub_word_separators` - The sub-word separators to use when classifying.
        """
        ...

    def rowcol(self, tp: int) -> Tuple[int, int]:
        """
        Calculates the 0-based line and column numbers of the point. Column numbers are returned as number of Unicode
        characters.
        """
        ...

    def rowcol_utf8(self, tp: int) -> Tuple[int, int]:
        """
        Calculates the 0-based line and column numbers of the point. Column numbers are returned as UTF-8 code units.
        """
        ...

    def rowcol_utf16(self, tp: int) -> Tuple[int, int]:
        """
        Calculates the 0-based line and column numbers of the point. Column numbers are returned as UTF-16 code units.
        """
        ...

    def text_point(self, row: int, col: int, *, clamp_column: bool = ...) -> int:
        """
        Calculates the character offset of the given, 0-based, `row` and `col`. `col` is interpreted as the number of
        Unicode characters to advance past the beginning of the row.

        - `clamp_column` - Whether `col` should be restricted to valid values for the given `row`.
        """
        ...

    def text_point_utf8(self, row: int, col_utf8: int, *, clamp_column: bool = ...) -> int:
        """
        Calculates the character offset of the given, 0-based, `row` and `col`. `col` is interpreted as the number of
        UTF-8 code units to advance past the beginning of the row.

        - `clamp_column` - Whether `col` should be restricted to valid values for the given `row`.
        """
        ...

    def text_point_utf16(self, row: int, col_utf16: int, *, clamp_column: bool = ...) -> int:
        """
        Calculates the character offset of the given, 0-based, `row` and `col`. `col` is interpreted as the number of
        UTF-16 code units to advance past the beginning of the row.

        - `clamp_column` - Whether `col` should be restricted to valid values for the given `row`.
        """
        ...

    def visible_region(self) -> Region:
        """
        The currently visible area of the view.
        """
        ...

    def show(
        self,
        x: Region | Selection | int,
        show_surrounds: bool = ...,
        keep_to_left: bool = ...,
        animate: bool = ...
    ) -> None:
        """
        Scroll the view to show the given location.

        - `location` - The location to scroll the view to. For a `Selection` only the first `Region` is shown.
        - `show_surrounds` - Whether to show the surrounding context around the location.
        - `keep_to_left` - Whether the view should be kept to the left, if horizontal scrolling is possible.
        - `animate` - Whether the scrolling should be animated.
        """
        ...

    def show_at_center(self, x: Region | int, animate: bool = ...) -> None:
        """
        Scroll the view to center on the location.

        - `x` - Which point or `Region` to scroll to.
        - `animate` - Whether the scrolling should be animated.
        """
        ...

    def viewport_position(self) -> Tuple[int, int]:
        """
        The offset of the viewport in layout coordinates.
        """
        ...

    def set_viewport_position(self, xy: Tuple[int, int], animate: bool = ...) -> None:
        """
        Scrolls the viewport to the given layout position.
        """
        ...

    def viewport_extent(self) -> Tuple[int, int]:
        """
        The width and height of the viewport.
        """
        ...

    def layout_extent(self) -> Tuple[int, int]:
        """
        The width and height of the layout.
        """
        ...

    def text_to_layout(self, tp: int) -> Tuple[int, int]:
        """
        Convert a text point to a layout position.
        """
        ...

    def text_to_window(self, tp: int) -> Tuple[int, int]:
        """
        Convert a text point to a window position.
        """
        ...

    def layout_to_text(self, xy: Tuple[int, int]) -> int:
        """
        Convert a layout position to a text point.
        """
        ...

    def layout_to_window(self, xy: Tuple[int, int]) -> Tuple[int, int]:
        """
        Convert a layout position to a window position.
        """
        ...

    def window_to_layout(self, xy: Tuple[int, int]) -> Tuple[int, int]:
        """
        Convert a window position to a layout position.
        """
        ...

    def window_to_text(self, xy: Tuple[int, int]) -> int:
        """
        Convert a window position to a text point.
        """
        ...

    def line_height(self) -> float:
        """
        The light height used in the layout.
        """
        ...

    def em_width(self) -> float:
        """
        The typical character width used in the layout.
        """
        ...

    def is_folded(self, sr: Region) -> bool:
        """
        Whether the provided `Region` is folded.
        """
        ...

    def folded_regions(self) -> List[Region]:
        """
        The list of folded regions.
        """
        ...

    def fold(self, x: Region | List[Region]) -> bool:
        """
        Fold the provided `Region`(s).

        Returns `False` if the regions were already folded.
        """
        ...

    def unfold(self, x: Region | List[Region]) -> List[Region]:
        """
        Unfold all text in the provided `Region`(s).

        Returns the unfolded regions.
        """
        ...

    def add_regions(
        self,
        key: str,
        regions: List[Region],
        scope: str = ...,
        icon: str = ...,
        flags: int = ...,
        annotations: List[str] = ...,
        annotation_color: str = ...,
        on_navigate: Callable[[str], None] = ...,
        on_close: Callable[[], None] = ...
    ) -> None:
        """
        Adds visual indicators to regions of text in the view. Indicators include icons in the gutter, underlines under
        the text, borders around the text and annotations. Annotations are drawn aligned to the right-hand edge of the
        view and may contain HTML markup.

        - `key` - An identifier for the collection of regions. If a set of regions already exists for this key they will
            be overridden.
        - `regions` - The list of regions to add. These should not overlap.
        - `scope` - An optional string used to source a color to draw the regions in. The scope is matched against the
            color scheme. Examples include: `"invalid"` and `"string"`.
            See [Scope Naming](https://www.sublimetext.com/docs/scope_naming.html) for a list of common scopes. If the
            scope is empty, the regions won't be drawn. Also supports the following pseudo-scopes, to allow picking the
            closest color from the user‘s color scheme:
                - `"region.redish"`
                - `"region.orangish"`
                - `"region.yellowish"`
                - `"region.greenish"`
                - `"region.cyanish"`
                - `"region.bluish"`
                - `"region.purplish"`
                - `"region.pinkish"`
        - `icon` - An optional string specifying an icon to draw in the gutter next to each region. The icon will be
            tinted using the color associated with the `scope`. Standard icon names are `"dot"`, `"circle"` and
            `"bookmark"`. The icon may also be a full package-relative path, such as
            `"Packages/Theme - Default/dot.png"`.
        - `flags` - Flags specifying how the region should be drawn, among other behavior.
        - `annotations` - An optional collection of strings containing HTML documents to display along the right-hand
            edge of the view. There should be the same number of annotations as regions. See minihtml for supported
            HTML.
        - `annotation_color` - An optional string of the CSS color to use when drawing the left border of the annotation.
            See [minihtml Reference: Colors](https://www.sublimetext.com/docs/minihtml.html#colors) for supported color
            formats.
        - `on_navigate` - Called when a link in an annotation is clicked. Will be passed the `href` of the link.
        - `on_close` - Called when the annotations are closed.
        """
        ...

    def get_regions(self, key: str) -> List[Region]:
        """
        The regions associated with the given `key`, if any.
        """
        ...

    def erase_regions(self, key: str) -> None:
        """
        Remove the regions associated with the given `key`.
        """
        ...

    # def add_phantom(
    #     self, key: str, region: Region, content: str, layout: int, on_navigate: Callable[[str], None] | None = ...
    # ) -> int:  # undocumented
    #     ...

    # def erase_phantoms(self, key: str) -> None:  # undocumented
    #     ...

    # def erase_phantom_by_id(self, pid: int) -> None:  # undocumented
    #     ...

    # def query_phantom(self, pid: int) -> List[Region]:  # undocumented
    #     ...

    # def query_phantoms(self, pids: List[int]) -> List[Region]:  # undocumented
    #     ...

    def assign_syntax(self, syntax: str | Syntax) -> None:
        """
        Changes the syntax used by the view. `syntax` may be a packages path to a syntax file, a `scope:` specifier
        string, or a `Syntax` object.
        """
        ...

    @deprecated("Use assign_syntax(...) instead")
    def set_syntax_file(self, syntax_file: str) -> None:
        ...

    def syntax(self) -> Any:
        """
        The syntax assigned to the buffer.
        """
        ...

    @deprecated("Use symbol_regions() instead")
    def symbols(self) -> List[Tuple[Region, str]]:
        ...

    @deprecated("Use symbol_regions() instead")
    def get_symbols(self) -> List[Tuple[Region, str]]:
        ...

    @deprecated("Use indexed_symbol_regions() instead")
    def indexed_symbols(self) -> List[Tuple[Region, str]]:
        ...

    @deprecated("Use indexed_symbol_regions() instead")
    def indexed_references(self) -> List[Tuple[Region, str]]:
        ...

    def symbol_regions(self) -> List[SymbolRegion]:
        """
        Info about symbols that are part of the view's symbol list.
        """
        ...

    def indexed_symbol_regions(self, type: int = ...) -> List[SymbolRegion]:
        """
        Info about symbols that are indexed.

        - `type` - The type of symbol to return.
        """
        ...

    def set_status(self, key: str, value: str) -> None:
        """
        Add the status `key` to the view. The `value` will be displayed in the status bar, in a comma separated list of
        all status values, ordered by key. Setting the `value` to `""` will clear the status.
        """
        ...

    def get_status(self, key: str) -> str:
        """
        The previous assigned value associated with the given `key`, if any.
        """
        ...

    def erase_status(self, key: str) -> None:
        """
        Clear the status associated with the provided `key`.
        """
        ...

    def extract_completions(self, prefix: str, tp: int = ...) -> List[str]:
        """
        Get a list of word-completions based on the contents of the view.

        - `prefix` - The prefix to filter words by.
        - `tp` - The point by which to weigh words. Closer words are preferred.
        """
        ...

    # def find_all_results(self) -> List[Tuple[str, int, int]]:  # undocumented
    #     ...

    # def find_all_results_with_text(self) -> List[Tuple[str, int, int]]:  # undocumented
    #     ...

    def command_history(self, delta: int, modifying_only: bool = ...) -> Tuple[Optional[str], Optional[dict], int]:
        """
        Get info on previous run commands stored in the undo/redo stack.

        - `delta` - The offset into the undo/redo stack. Positive values indicate to look in the redo stack for commands.
        - `modifying_only` - Whether only commands that modify the text buffer are considered.

        Returns the command name, command arguments and repeat count for the history entry. If the undo/redo history
        doesn't extend far enough, then `(None, None, 0)` will be returned.
        """
        ...

    def overwrite_status(self) -> bool:
        """
        The overwrite status, which the user normally toggles via the insert key.
        """
        ...

    def set_overwrite_status(self, value: bool) -> None:
        """
        Set the overwrite status.
        """
        ...

    def show_popup_menu(self, items: List[str], on_select: Callable[[int], None], flags: int = ...) -> None:
        """
        Show a popup menu at the caret, for selecting an item in a list.

        - `items` - The list of entries to show in the list.
        - `on_select` - Called once with the index of the selected item. If the popup was cancelled `-1` is passed
            instead.
        - `flags` - must be `0`, currently unused.
        """
        ...

    def show_popup(
        self,
        content: str,
        flags: int = ...,
        location: int = ...,
        max_width: int = ...,
        max_height: int = ...,
        on_navigate: Callable[[str], None] | None = ...,
        on_hide: Callable[[], None] | None = ...
    ) -> None:
        """
        Show a popup displaying HTML content.

        - `content` - The HTML content to display.
        - `flags` - Flags controlling popup behavior.
        - `location` - The point at which to display the popup. If `-1` the popup is shown at the current postion of the
            caret.
        - `max_width` - The maximum width of the popup.
        - `max_height` - The maximum height of the popup.
        - `on_navigate` - Called when a link is clicked in the popup. Passed the value of the `href` attribute of the
            clicked link.
        - `on_hide` - Called when the popup is hidden.
        """
        ...

    def update_popup(self, content: str) -> None:
        """
        Update the content of the currently visible popup.
        """
        ...

    def is_popup_visible(self) -> bool:
        """
        Whether a popup is currently shown.
        """
        ...

    def hide_popup(self) -> None:
        """
        Hide the current popup.
        """
        ...

    def is_auto_complete_visible(self) -> bool:
        """
        Whether the auto-complete menu is currently visible.
        """
        ...

    def preserve_auto_complete_on_focus_lost(self):
        """
        Sets the auto complete popup state to be preserved the next time the `View` loses focus. When the `View` regains
        focus, the auto complete window will be re-shown, with the previously selected entry pre-selected.
        """
        ...

    def export_to_html(
        self,
        regions=None,
        minihtml: bool = ...,
        enclosing_tags: bool = ...,
        font_size: bool = ...,
        font_family: bool = ...
    ) -> str:
        """
        Generates an HTML string of the current view contents, including styling for syntax highlighting.

        - `regions` - The region(s) to export. By default the whole view is exported.
        - `minihtml` - Whether the exported HTML should be compatible with minihtml.
        - `enclosing_tags` - Whether a `<div>` with base-styling is added. Note that without this no background color is
            set.
        - `font_size` - Whether to include the font size in the top level styling. Only applies when `enclosing_tags` is
            `True`.
        - `font_family` - Whether to include the font family in the top level styling. Only applies when `enclosing_tags`
            is `True`.
        """
        ...

    def clear_undo_stack(self) -> None:
        """
        Clear the undo/redo stack.
        """
        ...


class Buffer:
    """
    Represents a text buffer. Multiple `View` objects may share the same buffer.
    """
    buffer_id: int

    def __init__(self, id: int) -> None:
        ...

    def __eq__(self, other: object) -> bool:
        ...

    def id(self) -> int:
        """
        Returns a number that uniquely identifies this buffer.
        """
        ...

    def file_name(self) -> str | None:
        """
        The full name file the file associated with the buffer, or `None` if it doesn't exist on disk.
        """
        ...

    def views(self) -> List[View]:
        """
        Returns a list of all views that are associated with this buffer.
        """
        ...

    def primary_view(self) -> View:
        """
        The primary view associated with this buffer.
        """
        ...



class Settings:
    """
    A `dict` like object that a settings hierarchy.
    """
    settings_id: int

    def __init__(self, id: int) -> None:
        ...

    def get(
        self,
        key: str,
        default: bool | str | int | float | List[Any] | Dict[str, Any] | None = ...
    ) -> Any:
        """
        Returns the named setting.
        """
        ...

    def has(self, key: str) -> bool:
        """
        Returns whether the provided `key` is set.
        """
        ...

    def set(self, key: str, value: bool | str | int | float | List[Any] | Dict[str, Any] | None) -> None:
        """
        Set the named `key` to the provided `value`.
        """
        ...

    def erase(self, key: str) -> None:
        """
        Deletes the provided `key` from the setting. Note that a parent setting may also provide this key, thus deleting
        may not entirely remove a key.
        """
        ...

    def add_on_change(self, tag: str, callback: Callable[[], None]) -> None:
        """
        Register a callback to be run whenever a setting is changed.

        - `tag` - A string associated with the callback. For use with `clear_on_change`.
        - `callback` - A callable object to be run when a setting is changed.
        """
        ...

    def clear_on_change(self, tag: str) -> None:
        """
        Remove all callbacks associated with the provided `tag`. See `add_on_change`.
        """
        ...


class Phantom:
    """
    Represents an minihtml-based decoration to display non-editable content interspersed in a `View`. Used with
    `PhantomSet` to actually add the phantoms to the `View`. Once a `Phantom` has been constructed and added to the
    `View`, changes to the attributes will have no effect.
    """
    region: Region
    """The `Region` associated with the phantom. The phantom is displayed at the start of the `Region`."""
    content: str
    """The HTML content of the phantom."""
    layout: int
    """How the phantom should be placed relative to the `region`."""
    on_navigate: Callable[[str], None] | None
    """Called when a link in the HTML is clicked. The value of the `href` attribute is passed."""

    def __init__(
        self,
        region: Region,
        content: str,
        layout: int,
        on_navigate: Callable[[str], None] | None = ...
    ) -> None:
        ...

    def __eq__(self, rhs: 'Phantom') -> bool:
        ...

    def to_tuple(self) -> Tuple[Tuple[int, int], str, int, Optional[Callable[[str], None]]]:
        """
        Returns a tuple of this phantom containing the region, content, layout
        and callback.

        Use this to uniquely identify a phantom in a set or similar. Phantoms
        can't be used for that directly as they are mutable.
        """
        ...


class PhantomSet:
    """
    A collection that manages `Phantom` objects and the process of adding them, updating them and removing them from a
    `View`.
    """
    view: View
    """The `View` the phantom set is attached to."""
    key: str
    """A string used to group the phantoms together."""
    phantoms: List[Phantom]

    def __init__(self, view: View, key: str = ...) -> None:
        ...

    def __del__(self) -> None:
        ...

    def update(self, new_phantoms: Iterable[Phantom]) -> None:
        """
        Update the set of phantoms. If the `Phantom.region` of existing phantoms have changed they will be moved; new
        phantoms are added and ones not present are removed.
        """
        ...


class Html:
    """
    Used to indicate that a string is formatted as HTML.
    """
    data: str

    def __init__(
        self,
        data: str,
    ) -> None:
        ...


class CompletionList:
    """
    Represents a list of completions, some of which may be in the process of being asynchronously fetched.
    """
    target: Any
    completions: List[str] | List[Tuple[str, str]] | List[CompletionItem] | None
    flags: int

    def __init__(
        self,
        completions: List[str] | List[Tuple[str, str]] | List[CompletionItem] | None = ...,
        flags: int = ...
    ) -> None:
        """
        - `completions` - If `None` is passed, the method `set_completions()` must be called before the completions will
            be displayed to the user.
        - `flags` - Flags controlling auto-complete behavior.
        """
        ...

    def set_completions(self, completions: List[str] | List[Tuple[str, str]] | List[CompletionItem], flags: int = ...) -> None:
        """
        Sets the list of completions, allowing the list to be displayed to the user.
        """
        ...


class CompletionItem:
    """
    Represents an available auto-completion item.
    """
    trigger: str
    """Text to match against the user's input."""
    annotation: str
    """A hint to draw to the right-hand side of the trigger."""
    completion: str
    """Text to insert if the completion is specified. If empty the `trigger` will be inserted instead."""
    completion_format: int
    """The format of the completion."""
    kind: Tuple[int, str, str]
    """The kind of the completion."""
    details: str
    """
    An optional minihtml description of the completion, shown in the detail pane at the bottom of the auto complete
    window.
    """
    flags: int

    def __init__(
            self,
            trigger: str,
            annotation: str = ...,
            completion: str = ...,
            completion_format: int = ...,
            kind: Tuple[int, str, str] = ...,
            details: str = ...,
            flags: int = ...
        ) -> None:
        ...

    def __eq__(self, rhs: 'CompletionItem') -> bool:
        ...

    @classmethod
    def snippet_completion(
        cls,
        trigger: str,
        snippet: str,
        annotation: str = ...,
        kind: Tuple[int, str, str] = ...,
        details: str = ...
    ) -> 'CompletionItem':
        """
        Specialized constructor for snippet completions. The `completion_format` is always `COMPLETION_FORMAT_SNIPPET`.
        """
        ...

    @classmethod
    def command_completion(
        cls,
        trigger: str,
        command: str,
        args: Dict[str, Any] = ...,
        annotation: str = ...,
        kind: Tuple[int, str, str] = ...,
        details: str = ...
    ) -> 'CompletionItem':
        """
        Specialized constructor for command completions. The `completion_format` is always `COMPLETION_FORMAT_COMMAND`.
        """
        ...


def list_syntaxes() -> List[Syntax]:
    """List all known syntaxes.

    Returns a list of `Syntax`.
    """
    ...


def syntax_from_path(path: str) -> Syntax | None:
    """Get the syntax for a specific path.

    Returns a Syntax or `None`.
    """
    ...


def find_syntax_by_name(name: str) -> List[Syntax]:
    """Find syntaxes with the specified name.

    Name must match exactly. Return a list of `Syntax`.
    """
    ...


def find_syntax_by_scope(scope: str) -> List[Syntax]:
    """Find syntaxes with the specified scope.

    Scope must match exactly. Return a list of `Syntax`.
    """
    ...


def find_syntax_for_file(path: str, first_line: str = ...) -> Syntax | None:
    """Find the syntax to use for a path.

    Uses the file extension, various application settings and optionally the
    first line of the file to pick the right syntax for the file.

    Returns a `Syntax`.
    """
    ...


class Syntax:
    """
    Contains information about a syntax.
    """
    path: str
    """The packages path to the syntax file."""
    name: str
    """The name of the syntax."""
    hidden: bool
    """If the syntax is hidden from the user."""
    scope: str
    """The base scope name of the syntax."""

    def __init__(self, path: str, name: str, hidden: bool, scope: str) -> None:
        ...

    def __eq__(self, other: object) -> bool:
        ...


class QuickPanelItem:
    """
    Represents a row in the quick panel, shown via `Window.show_quick_panel()`.
    """
    trigger: str
    """Text to match against user's input."""
    details: str | List[str] | Tuple[str]
    """A minihtml string or list of strings displayed below the trigger."""
    annotation: str
    """Hint to draw to the right-hand side of the row."""
    kind: Tuple[int, str, str]
    """The kind of the item."""

    def __init__(
        self,
        trigger: str,
        details: str | Sequence[str] = ...,
        annotation: str = ...,
        kind: Tuple[int, str, str] = ...
    ) -> None:
        ...


class ListInputItem:
    """
    Represents a row shown via `ListInputHandler`.
    """
    text: str
    """Text to match against the user's input."""
    value: Any
    """A `Value` passed to the command if the row is selected."""
    details: str | List[str] | Tuple[str]
    """A minihtml string or list of strings displayed below the trigger."""
    annotation: str
    """Hint to draw to the right-hand side of the row."""
    kind: Tuple[int, str, str]
    """The kind of the item."""

    def __init__(
        self,
        text: str,
        value: bool | str | int | float | List[Any] | Dict[str, Any] | None,
        details: str | Sequence[str] = ...,
        annotation: str = ...,
        kind: Tuple[int, str, str] = ...
    ) -> None:
        ...


class SymbolRegion:
    """
    Contains information about a `Region` of a `View` that contains a symbol.
    """
    name: str
    """The name of the symbol."""
    region: Region
    """The location of the symbol within the `View`."""
    syntax: str
    """The name of the syntax for the symbol."""
    type: int
    """The type of the symbol"""
    kind: Tuple[int, str, str]
    """The kind of the symbol."""

    def __init__(self, name: str, region: Region, syntax: str, type: int, kind: Tuple[int, str, str]) -> None:
        ...


class SymbolLocation:
    """
    Contains information about a file that contains a symbol.
    """
    path: str
    """The filesystem path to the file containing the symbol."""
    display_name: str
    """The project-relative path to the file containing the symbol."""
    row: int
    """The row of the file the symbol is contained on."""
    col: int
    """The column of the row that the symbol is contained on."""
    syntax: str
    """The name of the syntax for the symbol."""
    type: int
    """The type of the symbol."""
    kind: Tuple[int, str, str]
    """The kind of the symbol."""

    def __init__(
        self,
        path: str,
        display_name: str,
        row: int,
        col: int,
        syntax: str,
        type: int,
        kind: Tuple[int, str, str]
    ) -> None:
        ...

    def path_encoded_position(self) -> str:
        ...
