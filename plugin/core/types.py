from __future__ import annotations
from .collections import DottedDict
from .file_watcher import FileWatcherEventType
from .logging import debug, set_debug_logging
from .protocol import ServerCapabilities, TextDocumentSyncKind, TextDocumentSyncOptions
from .url import filename_to_uri
from .url import parse_uri
from typing import Any, Callable, Dict, Generator, Iterable, List, Optional, TypedDict, TypeVar, Union
from typing import cast
from wcmatch.glob import BRACE
from wcmatch.glob import globmatch
from wcmatch.glob import GLOBSTAR
import contextlib
import fnmatch
import os
import posixpath
import socket
import sublime
import time


TCP_CONNECT_TIMEOUT = 5  # seconds
FEATURES_TIMEOUT = 300  # milliseconds
WORKSPACE_DIAGNOSTICS_TIMEOUT = 3000  # milliseconds

PANEL_FILE_REGEX = r"^(\S.*):$"
PANEL_LINE_REGEX = r"^\s+(\d+):(\d+)"

FileWatcherConfig = TypedDict("FileWatcherConfig", {
    "patterns": List[str],
    "events": Optional[List[FileWatcherEventType]],
    "ignores": Optional[List[str]],
}, total=False)


def basescope2languageid(base_scope: str) -> str:
    # This the connection between Language IDs and ST selectors.
    base_scope_map = sublime.load_settings("language-ids.sublime-settings")
    result = ""
    # Try to find exact match or less specific match consisting of at least 2 components.
    scope_parts = base_scope.split('.')
    while len(scope_parts) >= 2:
        result = base_scope_map.get('.'.join(scope_parts))
        if result:
            break
        scope_parts.pop()
    if not result:
        # If no match, use the second component of the scope as the language ID.
        scope_parts = base_scope.split('.')
        result = scope_parts[1] if len(scope_parts) > 1 else scope_parts[0]
    return result if isinstance(result, str) else ""


@contextlib.contextmanager
def runtime(token: str) -> Generator[None, None, None]:
    t = time.time()
    yield
    debug(token, "running time:", int((time.time() - t) * 1000000), "μs")


T = TypeVar("T")


def diff(old: Iterable[T], new: Iterable[T]) -> tuple[set[T], set[T]]:
    """
    Return a tuple of (added, removed) items
    """
    old_set = old if isinstance(old, set) else set(old)
    new_set = new if isinstance(new, set) else set(new)
    added = new_set - old_set
    removed = old_set - new_set
    return added, removed


def matches_pattern(path: str, patterns: Any) -> bool:
    if not isinstance(patterns, list):
        return False
    for pattern in patterns:
        if not isinstance(pattern, str):
            continue
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def sublime_pattern_to_glob(pattern: str, is_directory_pattern: bool, root_path: str | None = None) -> str:
    """
    Convert a Sublime Text pattern (http://www.sublimetext.com/docs/file_patterns.html)
    to a glob pattern that utilizes globstar extension.
    """
    glob = pattern
    if '/' not in glob:  # basic pattern: compared against exact file or directory name
        glob = f'**/{glob}'
        if is_directory_pattern:
            glob += '/**'
    else:  # complex pattern
        # With '*/' prefix or '/*' suffix, the '*' matches '/' characters.
        if glob.startswith('*/'):
            glob = f'*{glob}'
        if glob.endswith('/*'):
            glob += '*'
        # If a pattern ends in '/' it will be treated as a directory pattern, and will match both a directory with that
        # name and any contained files or subdirectories.
        if glob.endswith('/'):
            glob += '**'
        # If pattern begins with '//', it will be compared as a relative path from the project root.
        if glob.startswith('//') and root_path:
            glob = posixpath.join(root_path, glob[2:])
        # If a pattern begins with a single /, it will be treated as an absolute path.
        if not glob.startswith('/') and not glob.startswith('**/'):
            glob = f'**/{glob}'
        if is_directory_pattern and not glob.endswith('/**'):
            glob += '/**'
    return glob


def debounced(f: Callable[[], Any], timeout_ms: int = 0, condition: Callable[[], bool] = lambda: True,
              async_thread: bool = False) -> None:
    """
    Possibly run a function at a later point in time, either on the async thread or on the main thread.

    :param      f:             The function to possibly run. Its return type is discarded.
    :param      timeout_ms:    The time in milliseconds after which to possibly to run the function
    :param      condition:     The condition that must evaluate to True in order to run the function
    :param      async_thread:  If true, run the function on the async worker thread, otherwise run the function on the
                               main thread
    """

    def run() -> None:
        if condition():
            f()

    runner = sublime.set_timeout_async if async_thread else sublime.set_timeout
    runner(run, timeout_ms)


class SettingsRegistration:
    __slots__ = ("_settings",)

    def __init__(self, settings: sublime.Settings, on_change: Callable[[], None]) -> None:
        self._settings = settings
        settings.add_on_change("LSP", on_change)

    def __del__(self) -> None:
        self._settings.clear_on_change("LSP")


class DebouncerNonThreadSafe:
    """
    Debouncer for delaying execution of a function until specified timeout time.

    When calling `debounce()` multiple times, if the time span between calls is shorter than the specified `timeout_ms`,
    the callback function will only be called once, after `timeout_ms` since the last call.

    This implementation is not thread safe. You must ensure that `debounce()` is called from the same thread as
    was chosen during initialization through the `async_thread` argument.
    """

    def __init__(self, async_thread: bool) -> None:
        self._async_thread = async_thread
        self._current_id = -1
        self._next_id = 0

    def debounce(
        self, f: Callable[[], None], timeout_ms: int = 0, condition: Callable[[], bool] = lambda: True
    ) -> None:
        """
        Possibly run a function at a later point in time on the thread chosen during initialization.

        :param      f:             The function to possibly run
        :param      timeout_ms:    The time in milliseconds after which to possibly to run the function
        :param      condition:     The condition that must evaluate to True in order to run the function
        """

        def run(debounce_id: int) -> None:
            if debounce_id != self._current_id:
                return
            if condition():
                f()

        runner = sublime.set_timeout_async if self._async_thread else sublime.set_timeout
        current_id = self._current_id = self._next_id
        self._next_id += 1
        runner(lambda: run(current_id), timeout_ms)

    def cancel_pending(self) -> None:
        self._current_id = -1


def read_dict_setting(settings_obj: sublime.Settings, key: str, default: dict) -> dict:
    val = settings_obj.get(key)
    return val if isinstance(val, dict) else default


def read_list_setting(settings_obj: sublime.Settings, key: str, default: list) -> list:
    val = settings_obj.get(key)
    return val if isinstance(val, list) else default


class Settings:

    diagnostics_additional_delay_auto_complete_ms = cast(int, None)
    diagnostics_delay_ms = cast(int, None)
    diagnostics_gutter_marker = cast(str, None)
    diagnostics_highlight_style = cast(Union[str, Dict[str, str]], None)
    diagnostics_panel_include_severity_level = cast(int, None)
    disabled_capabilities = cast(List[str], None)
    document_highlight_style = cast(str, None)
    hover_highlight_style = cast(str, None)
    inhibit_snippet_completions = cast(bool, None)
    inhibit_word_completions = cast(bool, None)
    initially_folded = cast(List[str], None)
    link_highlight_style = cast(str, None)
    completion_insert_mode = cast(str, None)
    log_debug = cast(bool, None)
    log_max_size = cast(int, None)
    log_server = cast(List[str], None)
    lsp_code_actions_on_save = cast(Dict[str, bool], None)
    lsp_format_on_paste = cast(bool, None)
    lsp_format_on_save = cast(bool, None)
    on_save_task_timeout_ms = cast(int, None)
    only_show_lsp_completions = cast(bool, None)
    popup_max_characters_height = cast(int, None)
    popup_max_characters_width = cast(int, None)
    refactoring_auto_save = cast(str, None)
    semantic_highlighting = cast(bool, None)
    show_code_actions = cast(str, None)
    show_code_lens = cast(str, None)
    show_inlay_hints = cast(bool, None)
    inlay_hints_max_length = cast(int, None)
    show_diagnostics_in_hover = cast(bool, None)
    show_code_actions_in_hover = cast(bool, None)
    show_diagnostics_annotations_severity_level = cast(int, None)
    show_diagnostics_count_in_view_status = cast(bool, None)
    show_multiline_diagnostics_highlights = cast(bool, None)
    show_multiline_document_highlights = cast(bool, None)
    show_diagnostics_in_view_status = cast(bool, None)
    show_diagnostics_panel_on_save = cast(int, None)
    show_diagnostics_severity_level = cast(int, None)
    show_references_in_quick_panel = cast(bool, None)
    show_symbol_action_links = cast(bool, None)
    show_view_status = cast(bool, None)

    def __init__(self, s: sublime.Settings) -> None:
        self.update(s)

    def update(self, s: sublime.Settings) -> None:
        def r(name: str, default: bool | int | str | list | dict) -> None:
            val = s.get(name)
            setattr(self, name, val if isinstance(val, default.__class__) else default)

        r("diagnostics_additional_delay_auto_complete_ms", 0)
        r("diagnostics_delay_ms", 0)
        r("diagnostics_gutter_marker", "dot")
        r("diagnostics_panel_include_severity_level", 4)
        r("disabled_capabilities", [])
        r("document_highlight_style", "underline")
        r("hover_highlight_style", "")
        r("initially_folded", [])
        r("link_highlight_style", "underline")
        r("log_debug", False)
        r("log_max_size", 8 * 1024)
        r("lsp_code_actions_on_save", {})
        r("lsp_format_on_paste", False)
        r("lsp_format_on_save", False)
        r("on_save_task_timeout_ms", 2000)
        r("only_show_lsp_completions", False)
        r("completion_insert_mode", 'insert')
        r("popup_max_characters_height", 1000)
        r("popup_max_characters_width", 120)
        r("refactoring_auto_save", "never")
        r("semantic_highlighting", False)
        r("show_code_actions", "annotation")
        r("show_code_lens", "annotation")
        r("show_inlay_hints", False)
        r("inlay_hints_max_length", 30)
        r("show_diagnostics_in_hover", True)
        r("show_code_actions_in_hover", True)
        r("show_diagnostics_annotations_severity_level", 0)
        r("show_diagnostics_count_in_view_status", False)
        r("show_diagnostics_in_view_status", True)
        r("show_multiline_diagnostics_highlights", True)
        r("show_multiline_document_highlights", True)
        r("show_diagnostics_panel_on_save", 0)
        r("show_diagnostics_severity_level", 2)
        r("show_references_in_quick_panel", True)
        r("show_symbol_action_links", False)
        r("show_view_status", True)

        # Backwards-compatible with the bool setting
        log_server = s.get("log_server")
        if isinstance(log_server, bool):
            self.log_server = ["panel"] if log_server else []
        elif isinstance(log_server, list):
            self.log_server = log_server
        else:
            self.log_server = []

        # Backwards-compatible with the bool setting
        auto_show_diagnostics_panel = s.get("auto_show_diagnostics_panel")
        if isinstance(auto_show_diagnostics_panel, bool):
            if not auto_show_diagnostics_panel:
                self.show_diagnostics_panel_on_save = 0
        elif isinstance(auto_show_diagnostics_panel, str):
            if auto_show_diagnostics_panel == "never":
                self.show_diagnostics_panel_on_save = 0

        # Backwards-compatible with "only_show_lsp_completions"
        only_show_lsp_completions = s.get("only_show_lsp_completions")
        if isinstance(only_show_lsp_completions, bool):
            self.inhibit_snippet_completions = only_show_lsp_completions
            self.inhibit_word_completions = only_show_lsp_completions
        else:
            r("inhibit_snippet_completions", False)
            r("inhibit_word_completions", True)

        # correctness checking will happen inside diagnostics_highlight_style_flags method
        self.diagnostics_highlight_style = s.get("diagnostics_highlight_style")  # type: ignore

        # Backwards-compatible with "show_diagnostics_highlights"
        if s.get("show_diagnostics_highlights") is False:
            self.diagnostics_highlight_style = ""

        # Backwards-compatible with "code_action_on_save_timeout_ms"
        code_action_on_save_timeout_ms = s.get("code_action_on_save_timeout_ms")
        if isinstance(code_action_on_save_timeout_ms, int):
            self.on_save_task_timeout_ms = code_action_on_save_timeout_ms

        set_debug_logging(self.log_debug)

    def highlight_style_region_flags(self, style_str: str) -> tuple[sublime.RegionFlags, sublime.RegionFlags]:
        default = sublime.RegionFlags.NO_UNDO
        if style_str in ("background", "fill"):  # Backwards-compatible with "fill"
            style = default | sublime.RegionFlags.DRAW_NO_OUTLINE
            return style, style
        if style_str == "outline":
            style = default | sublime.RegionFlags.DRAW_NO_FILL
            return style, style
        if style_str == "stippled":
            return default | sublime.RegionFlags.DRAW_NO_FILL, default | sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.DRAW_NO_OUTLINE | sublime.RegionFlags.DRAW_STIPPLED_UNDERLINE  # noqa: E501
        return default | sublime.RegionFlags.DRAW_NO_FILL, default | sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.DRAW_NO_OUTLINE | sublime.RegionFlags.DRAW_SOLID_UNDERLINE  # noqa: E501

    @staticmethod
    def _style_str_to_flag(style_str: str) -> sublime.RegionFlags | None:
        default = sublime.RegionFlags.DRAW_EMPTY_AS_OVERWRITE | sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.NO_UNDO  # noqa: E501
        # This method could be a dict or lru_cache
        if style_str == "":
            return default | sublime.RegionFlags.DRAW_NO_OUTLINE
        if style_str == "box":
            return default
        if style_str == "underline":
            return default | sublime.RegionFlags.DRAW_NO_OUTLINE | sublime.RegionFlags.DRAW_SOLID_UNDERLINE
        if style_str == "stippled":
            return default | sublime.RegionFlags.DRAW_NO_OUTLINE | sublime.RegionFlags.DRAW_STIPPLED_UNDERLINE
        if style_str == "squiggly":
            return default | sublime.RegionFlags.DRAW_NO_OUTLINE | sublime.RegionFlags.DRAW_SQUIGGLY_UNDERLINE
        # default style (includes NO_UNDO)
        return None

    def diagnostics_highlight_style_flags(self) -> list[sublime.RegionFlags | None]:
        """Returns flags for highlighting diagnostics on single lines per severity"""
        if isinstance(self.diagnostics_highlight_style, str):
            # same style for all severity levels
            return [self._style_str_to_flag(self.diagnostics_highlight_style)] * 4
        elif isinstance(self.diagnostics_highlight_style, dict):
            flags: list[sublime.RegionFlags | None] = []
            for sev in ("error", "warning", "info", "hint"):
                user_style = self.diagnostics_highlight_style.get(sev)
                if user_style is None:  # user did not provide a style
                    flags.append(None)  # default styling, see comment below
                else:
                    flags.append(self._style_str_to_flag(user_style))
            return flags
        else:
            # Defaults are defined in DIAGNOSTIC_SEVERITY in plugin/core/views.py
            return [None] * 4  # default styling


class ClientStates:
    STARTING = 0
    READY = 1
    STOPPING = 2


class DocumentFilter:
    """
    A document filter denotes a document through properties like language, scheme or pattern. An example is a filter
    that applies to TypeScript files on disk. Another example is a filter that applies to JSON files with name
    package.json:

        { "language": "typescript", scheme: "file" }
        { "language": "json", "pattern": "**/package.json" }

    Sublime Text doesn't understand what a language ID is, so we have to maintain a global translation map from language
    IDs to selectors. Sublime Text also has no support for patterns. We use the wcmatch library for this.
    """

    __slots__ = ("language", "scheme", "pattern")

    def __init__(
        self,
        language: str | None = None,
        scheme: str | None = None,
        pattern: str | None = None
    ) -> None:
        self.scheme = scheme
        self.pattern = pattern
        self.language = language

    def __call__(self, view: sublime.View) -> bool:
        """Does this filter match the view? An empty filter matches any view."""
        if self.language:
            syntax = view.syntax()
            if not syntax or basescope2languageid(syntax.scope) != self.language:
                return False
        if self.scheme:
            uri = view.settings().get("lsp_uri")
            if isinstance(uri, str) and parse_uri(uri)[0] != self.scheme:
                return False
        if self.pattern:
            if not globmatch(view.file_name() or "", self.pattern, flags=GLOBSTAR | BRACE):
                return False
        return True


class DocumentSelector:
    """
    A DocumentSelector is a list of DocumentFilters. A view matches a DocumentSelector if and only if any one of its
    filters matches against the view.
    """

    __slots__ = ("filters",)

    def __init__(self, document_selector: list[dict[str, Any]]) -> None:
        self.filters = [DocumentFilter(**document_filter) for document_filter in document_selector]

    def __bool__(self) -> bool:
        return bool(self.filters)

    def matches(self, view: sublime.View) -> bool:
        """Does this selector match the view? A selector with no filters matches all views."""
        return any(f(view) for f in self.filters) if self.filters else True


# method -> (capability dotted path, optional registration dotted path)
# these are the EXCEPTIONS. The general rule is: method foo/bar --> (barProvider, barProvider.id)
_METHOD_TO_CAPABILITY_EXCEPTIONS: dict[str, tuple[str, str | None]] = {
    'workspace/symbol': ('workspaceSymbolProvider', None),
    'workspace/didChangeWorkspaceFolders': ('workspace.workspaceFolders',
                                            'workspace.workspaceFolders.changeNotifications'),
    'textDocument/didOpen': ('textDocumentSync.didOpen', None),
    'textDocument/didClose': ('textDocumentSync.didClose', None),
    'textDocument/didChange': ('textDocumentSync.change', None),
    'textDocument/didSave': ('textDocumentSync.save', None),
    'textDocument/willSave': ('textDocumentSync.willSave', None),
    'textDocument/willSaveWaitUntil': ('textDocumentSync.willSaveWaitUntil', None),
    'textDocument/formatting': ('documentFormattingProvider', None),
    'textDocument/documentColor': ('colorProvider', None)
}


def method_to_capability(method: str) -> tuple[str, str]:
    """
    Given a method, returns the corresponding capability path, and the associated path to stash the registration key.

    Examples:

        textDocument/definition --> (definitionProvider, definitionProvider.id)
        textDocument/references --> (referencesProvider, referencesProvider.id)
        textDocument/didOpen --> (textDocumentSync.didOpen, textDocumentSync.didOpen.id)
    """
    capability_path, registration_path = _METHOD_TO_CAPABILITY_EXCEPTIONS.get(method, (None, None))
    if capability_path is None:
        capability_path = method.split('/')[1] + "Provider"
    if registration_path is None:
        # This path happens to coincide with the StaticRegistrationOptions' id, which is on purpose. As a consequence,
        # if a server made a "registration" via the initialize response, it can call client/unregisterCapability at
        # a later date, and the capability will pop from the capabilities dict.
        registration_path = capability_path + ".id"
    return capability_path, registration_path


def normalize_text_sync(textsync: TextDocumentSyncOptions | TextDocumentSyncKind | None) -> dict[str, Any]:
    """
    Brings legacy text sync capabilities to the most modern format
    """
    result: dict[str, Any] = {}
    if isinstance(textsync, int):
        change = {"syncKind": textsync}
        result["textDocumentSync"] = {"didOpen": {}, "save": {}, "didClose": {}, "change": change}
    elif isinstance(textsync, dict):
        new = {}
        change = textsync.get("change")
        if isinstance(change, int):
            new["change"] = {"syncKind": change}
        elif isinstance(change, dict):
            new["change"] = change

        def maybe_assign_bool_or_dict(key: str) -> None:
            assert isinstance(textsync, dict)
            value = textsync.get(key)
            if isinstance(value, bool) and value:
                new[key] = {}
            elif isinstance(value, dict):
                new[key] = value

        open_close = textsync.get("openClose")
        if isinstance(open_close, bool):
            if open_close:
                new["didOpen"] = {}
                new["didClose"] = {}
        else:
            maybe_assign_bool_or_dict("didOpen")
            maybe_assign_bool_or_dict("didClose")
        maybe_assign_bool_or_dict("willSave")
        maybe_assign_bool_or_dict("willSaveWaitUntil")
        maybe_assign_bool_or_dict("save")
        result["textDocumentSync"] = new
    return result


class Capabilities(DottedDict):
    """
    Maintains static and dynamic capabilities

    Static capabilities come from a response to the initialize request (from Client -> Server).
    Dynamic capabilities can be registered at any moment with client/registerCapability and client/unregisterCapability
    (from Server -> Client).
    """

    def register(
        self,
        registration_id: str,
        capability_path: str,
        registration_path: str,
        options: dict[str, Any]
    ) -> None:
        stored_registration_id = self.get(registration_path)
        if isinstance(stored_registration_id, str):
            msg = "{} is already registered at {} with ID {}, overwriting"
            debug(msg.format(capability_path, registration_path, stored_registration_id))
        self.set(capability_path, options)
        self.set(registration_path, registration_id)

    def unregister(
        self,
        registration_id: str,
        capability_path: str,
        registration_path: str
    ) -> dict[str, Any] | None:
        stored_registration_id = self.get(registration_path)
        if not isinstance(stored_registration_id, str):
            debug("stored registration ID at", registration_path, "is not a string")
            return None
        elif stored_registration_id != registration_id:
            msg = "stored registration ID ({}) is not the same as the provided registration ID ({})"
            debug(msg.format(stored_registration_id, registration_id))
            return None
        else:
            discarded = self.get(capability_path)
            self.remove(capability_path)
            self.remove(registration_path)
            return discarded

    def assign(self, d: ServerCapabilities) -> None:
        textsync = normalize_text_sync(d.pop("textDocumentSync", None))
        super().assign(cast(dict, d))
        if textsync:
            self.update(textsync)

    def should_notify_did_open(self) -> bool:
        return "textDocumentSync.didOpen" in self

    def text_sync_kind(self) -> TextDocumentSyncKind:
        value: TextDocumentSyncKind = self.get("textDocumentSync.change.syncKind")
        return value if isinstance(value, int) else TextDocumentSyncKind.None_

    def should_notify_did_change_workspace_folders(self) -> bool:
        return "workspace.workspaceFolders.changeNotifications" in self

    def should_notify_will_save(self) -> bool:
        return "textDocumentSync.willSave" in self

    def should_notify_did_save(self) -> tuple[bool, bool]:
        save = self.get("textDocumentSync.save")
        if isinstance(save, bool):
            return save, False
        elif isinstance(save, dict):
            return True, bool(save.get("includeText"))
        else:
            return False, False

    def should_notify_did_close(self) -> bool:
        return "textDocumentSync.didClose" in self


def _translate_path(path: str, source: str, destination: str) -> tuple[str, bool]:
    # TODO: Case-insensitive file systems. Maybe this problem needs a much larger refactor. Even Sublime Text doesn't
    # handle case-insensitive file systems correctly. There are a few other places where case-sensitivity matters, for
    # example when looking up the correct view for diagnostics, and when finding a view for goto-def.
    if path.startswith(source) and len(path) > len(source) and path[len(source)] in ("/", "\\"):
        return path.replace(source, destination, 1), True
    return path, False


class PathMap:

    __slots__ = ("_local", "_remote")

    def __init__(self, local: str, remote: str) -> None:
        self._local = local
        self._remote = remote

    @classmethod
    def parse(cls, json: Any) -> list[PathMap] | None:
        if not isinstance(json, list):
            return None
        result: list[PathMap] = []
        for path_map in json:
            if not isinstance(path_map, dict):
                debug('path map entry is not an object')
                continue
            local = path_map.get("local")
            if not isinstance(local, str):
                debug('missing "local" key for path map entry')
                continue
            remote = path_map.get("remote")
            if not isinstance(remote, str):
                debug('missing "remote" key for path map entry')
                continue
            result.append(PathMap(local, remote))
        return result

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, PathMap):
            return False
        return self._local == other._local and self._remote == other._remote

    def map_from_local_to_remote(self, uri: str) -> tuple[str, bool]:
        return _translate_path(uri, self._local, self._remote)

    def map_from_remote_to_local(self, uri: str) -> tuple[str, bool]:
        return _translate_path(uri, self._remote, self._local)


class TransportConfig:
    __slots__ = ("name", "command", "tcp_port", "env", "listener_socket")

    def __init__(
        self,
        name: str,
        command: list[str],
        tcp_port: int | None,
        env: dict[str, str],
        listener_socket: socket.socket | None
    ) -> None:
        if not command and not tcp_port:
            raise ValueError('neither "command" nor "tcp_port" is provided; cannot start a language server')
        self.name = name
        self.command = command
        self.tcp_port = tcp_port
        self.env = env
        self.listener_socket = listener_socket


class ClientConfig:
    def __init__(self,
                 name: str,
                 selector: str,
                 priority_selector: str | None = None,
                 schemes: list[str] | None = None,
                 command: list[str] | None = None,
                 binary_args: list[str] | None = None,  # DEPRECATED
                 tcp_port: int | None = None,
                 auto_complete_selector: str | None = None,
                 enabled: bool = True,
                 init_options: DottedDict = DottedDict(),
                 settings: DottedDict = DottedDict(),
                 env: dict[str, str | list[str]] = {},
                 experimental_capabilities: dict[str, Any] | None = None,
                 disabled_capabilities: DottedDict = DottedDict(),
                 file_watcher: FileWatcherConfig = {},
                 semantic_tokens: dict[str, str] | None = None,
                 diagnostics_mode: str = "open_files",
                 path_maps: list[PathMap] | None = None) -> None:
        self.name = name
        self.selector = selector
        self.priority_selector = priority_selector if priority_selector else self.selector
        if isinstance(schemes, list):
            self.schemes: list[str] = schemes
        else:
            self.schemes = ["file"]
        if isinstance(command, list):
            self.command = command
        else:
            assert isinstance(binary_args, list)
            self.command = binary_args
        self.tcp_port = tcp_port
        self.auto_complete_selector = auto_complete_selector
        self.enabled = enabled
        self.init_options = init_options
        self.settings = settings
        self.env = env
        self.experimental_capabilities = experimental_capabilities
        self.disabled_capabilities = disabled_capabilities
        self.file_watcher = file_watcher
        self.path_maps = path_maps
        self.status_key = f"lsp_{self.name}"
        self.semantic_tokens = semantic_tokens
        self.diagnostics_mode = diagnostics_mode

    @classmethod
    def from_sublime_settings(cls, name: str, s: sublime.Settings, file: str) -> ClientConfig:
        base = sublime.decode_value(sublime.load_resource(file))
        settings = DottedDict(base.get("settings", {}))  # defined by the plugin author
        settings.update(read_dict_setting(s, "settings", {}))  # overrides from the user
        init_options = DottedDict(base.get("initializationOptions", {}))
        init_options.update(read_dict_setting(s, "initializationOptions", {}))
        disabled_capabilities = s.get("disabled_capabilities")
        file_watcher = cast(FileWatcherConfig, read_dict_setting(s, "file_watcher", {}))
        semantic_tokens = read_dict_setting(s, "semantic_tokens", {})
        if isinstance(disabled_capabilities, dict):
            disabled_capabilities = DottedDict(disabled_capabilities)
        else:
            disabled_capabilities = DottedDict()
        return ClientConfig(
            name=name,
            selector=_read_selector(s),
            priority_selector=_read_priority_selector(s),
            schemes=s.get("schemes"),
            command=read_list_setting(s, "command", []),
            tcp_port=s.get("tcp_port"),
            auto_complete_selector=s.get("auto_complete_selector"),
            # Default to True, because an LSP plugin is enabled iff it is enabled as a Sublime package.
            enabled=bool(s.get("enabled", True)),
            init_options=init_options,
            settings=settings,
            env=read_dict_setting(s, "env", {}),
            experimental_capabilities=s.get("experimental_capabilities"),
            disabled_capabilities=disabled_capabilities,
            file_watcher=file_watcher,
            semantic_tokens=semantic_tokens,
            diagnostics_mode=str(s.get("diagnostics_mode", "open_files")),
            path_maps=PathMap.parse(s.get("path_maps"))
        )

    @classmethod
    def from_dict(cls, name: str, d: dict[str, Any]) -> ClientConfig:
        disabled_capabilities = d.get("disabled_capabilities")
        if isinstance(disabled_capabilities, dict):
            disabled_capabilities = DottedDict(disabled_capabilities)
        else:
            disabled_capabilities = DottedDict()
        schemes = d.get("schemes")
        if not isinstance(schemes, list):
            schemes = ["file"]
        return ClientConfig(
            name=name,
            selector=_read_selector(d),
            priority_selector=_read_priority_selector(d),
            schemes=schemes,
            command=d.get("command", []),
            tcp_port=d.get("tcp_port"),
            auto_complete_selector=d.get("auto_complete_selector"),
            enabled=d.get("enabled", False),
            init_options=DottedDict(d.get("initializationOptions")),
            settings=DottedDict(d.get("settings")),
            env=d.get("env", dict()),
            experimental_capabilities=d.get("experimental_capabilities"),
            disabled_capabilities=disabled_capabilities,
            file_watcher=d.get("file_watcher", dict()),
            semantic_tokens=d.get("semantic_tokens", dict()),
            diagnostics_mode=d.get("diagnostics_mode", "open_files"),
            path_maps=PathMap.parse(d.get("path_maps"))
        )

    @classmethod
    def from_config(cls, src_config: ClientConfig, override: dict[str, Any]) -> ClientConfig:
        path_map_override = PathMap.parse(override.get("path_maps"))
        disabled_capabilities = override.get("disabled_capabilities")
        if isinstance(disabled_capabilities, dict):
            disabled_capabilities = DottedDict(disabled_capabilities)
        else:
            disabled_capabilities = src_config.disabled_capabilities
        return ClientConfig(
            name=src_config.name,
            selector=_read_selector(override) or src_config.selector,
            priority_selector=_read_priority_selector(override) or src_config.priority_selector,
            schemes=override.get("schemes", src_config.schemes),
            command=override.get("command", src_config.command),
            tcp_port=override.get("tcp_port", src_config.tcp_port),
            auto_complete_selector=override.get("auto_complete_selector", src_config.auto_complete_selector),
            enabled=override.get("enabled", src_config.enabled),
            init_options=DottedDict.from_base_and_override(
                src_config.init_options, override.get("initializationOptions")),
            settings=DottedDict.from_base_and_override(src_config.settings, override.get("settings")),
            env=override.get("env", src_config.env),
            experimental_capabilities=override.get(
                "experimental_capabilities", src_config.experimental_capabilities),
            disabled_capabilities=disabled_capabilities,
            file_watcher=override.get("file_watcher", src_config.file_watcher),
            semantic_tokens=override.get("semantic_tokens", src_config.semantic_tokens),
            diagnostics_mode=override.get("diagnostics_mode", src_config.diagnostics_mode),
            path_maps=path_map_override if path_map_override else src_config.path_maps
        )

    def resolve_transport_config(self, variables: dict[str, str]) -> TransportConfig:
        tcp_port: int | None = None
        listener_socket: socket.socket | None = None
        if self.tcp_port is not None:
            # < 0 means we're hosting a TCP server
            if self.tcp_port < 0:
                # -1 means pick any free port
                if self.tcp_port < -1:
                    tcp_port = -self.tcp_port
                # Create a listener socket for incoming connections
                listener_socket = _start_tcp_listener(tcp_port)
                tcp_port = int(listener_socket.getsockname()[1])
            else:
                tcp_port = _find_free_port() if self.tcp_port == 0 else self.tcp_port
        if tcp_port is not None:
            variables["port"] = str(tcp_port)
        command = sublime.expand_variables(self.command, variables)
        command = [os.path.expanduser(arg) for arg in command]
        if tcp_port is not None:
            # DEPRECATED -- replace {port} with $port or ${port} in your client config
            command = [a.replace('{port}', str(tcp_port)) for a in command]
        env = os.environ.copy()
        for key, value in self.env.items():
            if isinstance(value, list):
                value = os.path.pathsep.join(value)
            if key == 'PATH':
                env[key] = sublime.expand_variables(value, variables) + os.path.pathsep + env[key]
            else:
                env[key] = sublime.expand_variables(value, variables)
        return TransportConfig(self.name, command, tcp_port, env, listener_socket)

    def set_view_status(self, view: sublime.View, message: str) -> None:
        if sublime.load_settings("LSP.sublime-settings").get("show_view_status"):
            status = f"{self.name} ({message})" if message else self.name
            view.set_status(self.status_key, status)
        else:
            self.erase_view_status(view)

    def erase_view_status(self, view: sublime.View) -> None:
        view.erase_status(self.status_key)

    def match_view(self, view: sublime.View, scheme: str) -> bool:
        syntax = view.syntax()
        if not syntax:
            return False
        selector = self.selector.strip()
        if not selector:
            return False
        return scheme in self.schemes and sublime.score_selector(syntax.scope, selector) > 0

    def map_client_path_to_server_uri(self, path: str) -> str:
        if self.path_maps:
            for path_map in self.path_maps:
                path, mapped = path_map.map_from_local_to_remote(path)
                if mapped:
                    break
        return filename_to_uri(path)

    def map_server_uri_to_client_path(self, uri: str) -> str:
        scheme, path = parse_uri(uri)
        if scheme not in ("file", "res"):
            raise ValueError(f"{uri}: {scheme} URI scheme is unsupported")
        if self.path_maps:
            for path_map in self.path_maps:
                path, mapped = path_map.map_from_remote_to_local(path)
                if mapped:
                    break
        return path

    def is_disabled_capability(self, capability_path: str) -> bool:
        for value in self.disabled_capabilities.walk(capability_path):
            if isinstance(value, bool):
                return value
            elif isinstance(value, dict):
                if value:
                    # If it's not empty we'll continue the walk
                    continue
                else:
                    # This might be a leaf node
                    return True
        return False

    def filter_out_disabled_capabilities(self, capability_path: str, options: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for k, v in options.items():
            if not self.is_disabled_capability(f"{capability_path}.{k}"):
                result[k] = v
        return result

    def __repr__(self) -> str:
        items: list[str] = []
        for k, v in self.__dict__.items():
            if not k.startswith("_"):
                items.append(f"{k}={repr(v)}")
        return "{}({})".format(self.__class__.__name__, ", ".join(items))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ClientConfig):
            return False
        for k, v in self.__dict__.items():
            if not k.startswith("_") and v != getattr(other, k):
                return False
        return True


def syntax2scope(syntax_path: str) -> str | None:
    syntax = sublime.syntax_from_path(syntax_path)
    return syntax.scope if syntax else None


def view2scope(view: sublime.View) -> str:
    try:
        return view.scope_name(0).split()[0]
    except IndexError:
        return ''


def _read_selector(config: sublime.Settings | dict[str, Any]) -> str:
    # Best base scenario,
    selector = config.get("selector")
    if isinstance(selector, str):
        return selector
    # Otherwise, look for "languages": [...]
    languages = config.get("languages")
    if isinstance(languages, list):
        selectors = []
        for language in languages:
            # First priority is document_selector,
            document_selector = language.get("document_selector")
            if isinstance(document_selector, str):
                selectors.append(document_selector)
                continue
            # After that syntaxes has priority,
            syntaxes = language.get("syntaxes")
            if isinstance(syntaxes, list):
                for path in syntaxes:
                    syntax = sublime.syntax_from_path(path)
                    if syntax:
                        selectors.append(syntax.scope)
                continue
            # No syntaxes and no document_selector... then there must exist a languageId.
            language_id = language.get("languageId")
            if isinstance(language_id, str):
                selectors.append(f"source.{language_id}")
        return "|".join(map("({})".format, selectors))
    # Otherwise, look for "document_selector"
    document_selector = config.get("document_selector")
    if isinstance(document_selector, str):
        return document_selector
    # Otherwise, look for "syntaxes": [...]
    syntaxes = config.get("syntaxes")
    if isinstance(syntaxes, list):
        selectors = []
        for path in syntaxes:
            syntax = sublime.syntax_from_path(path)
            if syntax:
                selectors.append(syntax.scope)
        return "|".join(selectors)
    # No syntaxes and no document_selector... then there must exist a languageId.
    language_id = config.get("languageId")
    if language_id:
        return f"source.{language_id}"
    return ""


def _read_priority_selector(config: sublime.Settings | dict[str, Any]) -> str:
    # Best case scenario
    selector = config.get("priority_selector")
    if isinstance(selector, str):
        return selector
    # Otherwise, look for "languages": [...]
    languages = config.get("languages")
    if isinstance(languages, list):
        selectors = []
        for language in languages:
            # First priority is feature_selector.
            feature_selector = language.get("feature_selector")
            if isinstance(feature_selector, str):
                selectors.append(feature_selector)
                continue
            # After that scopes has priority.
            scopes = language.get("scopes")
            if isinstance(scopes, list):
                selectors.extend(scopes)
                continue
            # No scopes and no feature_selector. So there must be a languageId
            language_id = language.get("languageId")
            if isinstance(language_id, str):
                selectors.append(f"source.{language_id}")
        return "|".join(map("({})".format, selectors))
    # Otherwise, look for "feature_selector"
    feature_selector = config.get("feature_selector")
    if isinstance(feature_selector, str):
        return feature_selector
    # Otherwise, look for "scopes": [...]
    scopes = config.get("scopes")
    if isinstance(scopes, list):
        return "|".join(map("({})".format, scopes))
    # No scopes and no feature_selector... then there must exist a languageId
    language_id = config.get("languageId")
    if language_id:
        return f"source.{language_id}"
    return ""


def _find_free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def _start_tcp_listener(tcp_port: int | None) -> socket.socket:
    sock = socket.socket()
    sock.bind(('localhost', tcp_port or 0))
    sock.settimeout(TCP_CONNECT_TIMEOUT)
    sock.listen(1)
    return sock
