from .collections import DottedDict
from .logging import debug, set_debug_logging
from .protocol import TextDocumentSyncKindNone
from .typing import Any, Optional, List, Dict, Generator, Callable, Iterable, Union, Set, Tuple, TypedDict, TypeVar
from threading import RLock
from wcmatch.glob import BRACE
from wcmatch.glob import globmatch
from wcmatch.glob import GLOBSTAR
import contextlib
import os
import socket
import sublime
import time


TCP_CONNECT_TIMEOUT = 5

CodeAction = TypedDict('CodeAction', {
    'title': str,
    'kind': Optional[str],
    'edit': Optional[dict],
    'command': Optional[Union[dict, str]],
}, total=False)


def basescope2languageid(base_scope: str) -> str:
    # This the connection between Language IDs and ST selectors.
    base_scope_map = sublime.load_settings("language-ids.sublime-settings")
    result = base_scope_map.get(base_scope, base_scope.split(".")[-1])
    return result if isinstance(result, str) else ""


@contextlib.contextmanager
def runtime(token: str) -> Generator[None, None, None]:
    t = time.time()
    yield
    debug(token, "running time:", int((time.time() - t) * 1000000), "μs")


T = TypeVar("T")


def diff(old: Iterable[T], new: Iterable[T]) -> Tuple[Set[T], Set[T]]:
    """
    Return a tuple of (added, removed) items
    """
    old_set = old if isinstance(old, set) else set(old)
    new_set = new if isinstance(new, set) else set(new)
    added = new_set - old_set
    removed = old_set - new_set
    return added, removed


def debounced(f: Callable[[], None], timeout_ms: int = 0, condition: Callable[[], bool] = lambda: True,
              async_thread: bool = False) -> None:
    """
    Possibly run a function at a later point in time, either on the async thread or on the main thread.

    :param      f:             The function to possibly run
    :param      timeout_ms:    The time in milliseconds after which to possibly to run the function
    :param      condition:     The condition that must evaluate to True in order to run the funtion
    :param      async_thread:  If true, run the function on the async worker thread, otherwise run the function on the
                               main thread
    """

    def run() -> None:
        if condition():
            f()

    runner = sublime.set_timeout_async if async_thread else sublime.set_timeout
    runner(run, timeout_ms)


def _settings_style_to_add_regions_flag(style: str) -> int:
    flags = 0
    if style == "fill":
        pass
    elif style == "box":
        flags = sublime.DRAW_NO_FILL
    else:
        flags = sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE
        if style == "underline":
            flags |= sublime.DRAW_SOLID_UNDERLINE
        elif style == "stippled":
            flags |= sublime.DRAW_STIPPLED_UNDERLINE
        elif style == "squiggly":
            flags |= sublime.DRAW_SQUIGGLY_UNDERLINE
    return flags


class SettingsRegistration:
    __slots__ = ("_settings",)

    def __init__(self, settings: sublime.Settings, on_change: Callable[[], None]) -> None:
        self._settings = settings
        settings.add_on_change("LSP", on_change)

    def __del__(self) -> None:
        self._settings.clear_on_change("LSP")


class Debouncer:

    def __init__(self) -> None:
        self._current_id = -1
        self._next_id = 0
        self._current_id_lock = RLock()

    def debounce(self, f: Callable[[], None], timeout_ms: int = 0, condition: Callable[[], bool] = lambda: True,
                 async_thread: bool = False) -> None:
        """
        Possibly run a function at a later point in time, either on the async thread or on the main thread.

        :param      f:             The function to possibly run
        :param      timeout_ms:    The time in milliseconds after which to possibly to run the function
        :param      condition:     The condition that must evaluate to True in order to run the funtion
        :param      async_thread:  If true, run the function on the async worker thread, otherwise run
                                   the function on the main thread
        """

        def run(debounce_id: int) -> None:
            with self._current_id_lock:
                if debounce_id != self._current_id:
                    return
            if condition():
                f()

        runner = sublime.set_timeout_async if async_thread else sublime.set_timeout
        with self._current_id_lock:
            current_id = self._current_id = self._next_id
        self._next_id += 1
        runner(lambda: run(current_id), timeout_ms)

    def cancel_pending(self) -> None:
        with self._current_id_lock:
            self._current_id = -1


def read_dict_setting(settings_obj: sublime.Settings, key: str, default: dict) -> dict:
    val = settings_obj.get(key)
    return val if isinstance(val, dict) else default


def read_list_setting(settings_obj: sublime.Settings, key: str, default: list) -> list:
    val = settings_obj.get(key)
    return val if isinstance(val, list) else default


class Settings:

    # This is only for mypy
    auto_show_diagnostics_panel = None  # type: str
    auto_show_diagnostics_panel_level = None  # type: int
    code_action_on_save_timeout_ms = None  # type: int
    diagnostics_additional_delay_auto_complete_ms = None  # type: int
    diagnostics_delay_ms = None  # type: int
    diagnostics_gutter_marker = None  # type: str
    diagnostics_highlight_style = None  # type: str
    diagnostics_panel_include_severity_level = None  # type: int
    disabled_capabilities = None  # type: List[str]
    document_highlight_scopes = None  # type: Dict[str, str]
    document_highlight_style = None  # type: str
    inhibit_snippet_completions = None  # type: bool
    inhibit_word_completions = None  # type: bool
    log_debug = None  # type: bool
    log_max_size = None  # type: int
    log_server = None  # type: List[str]
    log_stderr = None  # type: bool
    lsp_code_actions_on_save = None  # type: Dict[str, bool]
    lsp_format_on_save = None  # type: bool
    only_show_lsp_completions = None  # type: bool
    show_code_actions = None  # type: bool
    show_diagnostics_count_in_view_status = None  # type: bool
    show_diagnostics_in_view_status = None  # type: bool
    show_diagnostics_severity_level = None  # type: int
    show_references_in_quick_panel = None  # type: bool
    show_symbol_action_links = None  # type: bool
    show_view_status = None  # type: bool

    def __init__(self, s: sublime.Settings) -> None:
        self.update(s)

    def update(self, s: sublime.Settings) -> None:

        def r(name: str, default: Union[bool, int, str, list, dict]) -> None:
            val = s.get(name)
            setattr(self, name, val if isinstance(val, default.__class__) else default)

        # r("auto_show_diagnostics_panel", "always")
        r("auto_show_diagnostics_panel_level", 2)
        r("code_action_on_save_timeout_ms", 2000)
        r("diagnostics_additional_delay_auto_complete_ms", 0)
        r("diagnostics_delay_ms", 0)
        r("diagnostics_gutter_marker", "dot")
        r("diagnostics_highlight_style", "underline")
        r("diagnostics_panel_include_severity_level", 4)
        r("disabled_capabilities", [])
        r("document_highlight_scopes", {"unknown": "text", "text": "text", "read": "markup.inserted", "write": "markup.changed"})  # noqa
        r("document_highlight_style", "stippled")
        r("log_debug", False)
        r("log_max_size", 8 * 1024)
        # r("log_server", [])
        r("log_stderr", False)
        r("lsp_code_actions_on_save", {})
        r("lsp_format_on_save", False)
        r("only_show_lsp_completions", False)
        r("show_code_actions", "annotation")
        r("show_diagnostics_count_in_view_status", False)
        r("show_diagnostics_in_view_status", True)
        r("show_diagnostics_severity_level", 2)
        r("show_references_in_quick_panel", False)
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
            self.auto_show_diagnostics_panel = "always" if auto_show_diagnostics_panel else "never"
        elif isinstance(auto_show_diagnostics_panel, str):
            self.auto_show_diagnostics_panel = auto_show_diagnostics_panel
        else:
            self.auto_show_diagnostics_panel = "always"

        # Backwards-compatible with "only_show_lsp_completions"
        only_show_lsp_completions = s.get("only_show_lsp_completions")
        if isinstance(only_show_lsp_completions, bool):
            self.inhibit_snippet_completions = only_show_lsp_completions
            self.inhibit_word_completions = only_show_lsp_completions
        else:
            r("inhibit_snippet_completions", False)
            r("inhibit_word_completions", True)

        set_debug_logging(self.log_debug)

    def show_diagnostics_panel_always(self) -> bool:
        return self.auto_show_diagnostics_panel == "always"

    def show_diagnostics_panel_on_save(self) -> bool:
        return self.auto_show_diagnostics_panel == "saved"

    def document_highlight_style_to_add_regions_flags(self) -> int:
        return _settings_style_to_add_regions_flag(self.document_highlight_style)

    def diagnostics_highlight_style_to_add_regions_flag(self) -> int:
        return _settings_style_to_add_regions_flag(self.diagnostics_highlight_style)


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
        language: Optional[str] = None,
        scheme: Optional[str] = None,
        pattern: Optional[str] = None
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
            # Can be "file" or "untitled"?
            pass
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

    def __init__(self, document_selector: List[Dict[str, Any]]) -> None:
        self.filters = [DocumentFilter(**document_filter) for document_filter in document_selector]

    def __bool__(self) -> bool:
        return bool(self.filters)

    def matches(self, view: sublime.View) -> bool:
        """Does this selector match the view? A selector with no filters matches all views."""
        return any(f(view) for f in self.filters) if self.filters else True


# method -> (capability dotted path, optional registration dotted path)
# these are the EXCEPTIONS. The general rule is: method foo/bar --> (barProvider, barProvider.id)
_METHOD_TO_CAPABILITY_EXCEPTIONS = {
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
}  # type: Dict[str, Tuple[str, Optional[str]]]


def method_to_capability(method: str) -> Tuple[str, str]:
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


def normalize_text_sync(textsync: Union[None, int, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Brings legacy text sync capabilities to the most modern format
    """
    result = {}  # type: Dict[str, Any]
    if isinstance(textsync, int):
        change = {"syncKind": textsync}  # type: Optional[Dict[str, Any]]
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
        options: Dict[str, Any]
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
    ) -> Optional[Dict[str, Any]]:
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

    def assign(self, d: Dict[str, Any]) -> None:
        textsync = normalize_text_sync(d.pop("textDocumentSync", None))
        super().assign(d)
        if textsync:
            self.update(textsync)

    def should_notify_did_open(self) -> bool:
        return "textDocumentSync.didOpen" in self

    def text_sync_kind(self) -> int:
        value = self.get("textDocumentSync.change.syncKind")
        return value if isinstance(value, int) else TextDocumentSyncKindNone

    def should_notify_did_change(self) -> bool:
        return self.text_sync_kind() > TextDocumentSyncKindNone

    def should_notify_did_change_workspace_folders(self) -> bool:
        return "workspace.workspaceFolders.changeNotifications" in self

    def should_notify_will_save(self) -> bool:
        return "textDocumentSync.willSave" in self

    def should_notify_did_save(self) -> Tuple[bool, bool]:
        save = self.get("textDocumentSync.save")
        if isinstance(save, bool):
            return save, False
        elif isinstance(save, dict):
            return True, bool(save.get("includeText"))
        else:
            return False, False

    def should_notify_did_close(self) -> bool:
        return "textDocumentSync.didClose" in self


class ResolvedStartupConfig:
    __slots__ = ("command", "tcp_port", "init_options", "env", "listener_socket")

    def __init__(
        self,
        command: List[str],
        tcp_port: Optional[int],
        init_options: DottedDict,
        env: Dict[str, str],
        listener_socket: Optional[socket.socket]
    ) -> None:
        self.command = command
        self.tcp_port = tcp_port
        self.init_options = init_options
        self.env = env
        self.listener_socket = listener_socket


class ClientConfig:
    def __init__(self,
                 name: str,
                 selector: str,
                 priority_selector: Optional[str] = None,
                 command: Optional[List[str]] = None,
                 binary_args: Optional[List[str]] = None,  # DEPRECATED
                 tcp_port: Optional[int] = None,
                 auto_complete_selector: Optional[str] = None,
                 ignore_server_trigger_chars: bool = False,
                 enabled: bool = True,
                 init_options: DottedDict = DottedDict(),
                 settings: DottedDict = DottedDict(),
                 env: Dict[str, str] = {},
                 experimental_capabilities: Optional[Dict[str, Any]] = None) -> None:
        self.name = name
        self.selector = selector
        self.priority_selector = priority_selector if priority_selector else self.selector
        if isinstance(command, list):
            self.command = command
        else:
            assert isinstance(binary_args, list)
            self.command = binary_args
        self.tcp_port = tcp_port
        self.auto_complete_selector = auto_complete_selector
        self.ignore_server_trigger_chars = ignore_server_trigger_chars
        self.enabled = enabled
        self.init_options = init_options
        self.settings = settings
        self.env = env
        self.experimental_capabilities = experimental_capabilities
        self.status_key = "lsp_{}".format(self.name)

    @classmethod
    def from_sublime_settings(cls, name: str, s: sublime.Settings, file: str) -> "ClientConfig":
        base = sublime.decode_value(sublime.load_resource(file))
        settings = DottedDict(base.get("settings", {}))  # defined by the plugin author
        settings.update(read_dict_setting(s, "settings", {}))  # overrides from the user
        init_options = DottedDict(base.get("initializationOptions", {}))
        init_options.update(read_dict_setting(s, "initializationOptions", {}))
        return ClientConfig(
            name=name,
            selector=_read_selector(s),
            priority_selector=_read_priority_selector(s),
            command=read_list_setting(s, "command", []),
            tcp_port=s.get("tcp_port"),
            auto_complete_selector=s.get("auto_complete_selector"),
            ignore_server_trigger_chars=bool(s.get("ignore_server_trigger_chars", False)),
            # Default to True, because an LSP plugin is enabled iff it is enabled as a Sublime package.
            enabled=bool(s.get("enabled", True)),
            init_options=init_options,
            settings=settings,
            env=read_dict_setting(s, "env", {}),
            experimental_capabilities=s.get("experimental_capabilities")
        )

    @classmethod
    def from_dict(cls, name: str, d: Dict[str, Any]) -> "ClientConfig":
        return ClientConfig(
            name=name,
            selector=_read_selector(d),
            priority_selector=_read_priority_selector(d),
            command=d.get("command", []),
            tcp_port=d.get("tcp_port"),
            auto_complete_selector=d.get("auto_complete_selector"),
            ignore_server_trigger_chars=bool(d.get("ignore_server_trigger_chars", False)),
            enabled=d.get("enabled", False),
            init_options=DottedDict(d.get("initializationOptions")),
            settings=DottedDict(d.get("settings")),
            env=d.get("env", dict()),
            experimental_capabilities=d.get("experimental_capabilities", dict())
        )

    def update(self, override: Dict[str, Any]) -> "ClientConfig":
        return ClientConfig(
            name=self.name,
            selector=_read_selector(override) or self.selector,
            priority_selector=_read_priority_selector(override) or self.priority_selector,
            command=override.get("command", self.command),
            tcp_port=override.get("tcp_port", self.tcp_port),
            auto_complete_selector=override.get("auto_complete_selector", self.auto_complete_selector),
            ignore_server_trigger_chars=bool(
                override.get("ignore_server_trigger_chars", self.ignore_server_trigger_chars)),
            enabled=override.get("enabled", self.enabled),
            init_options=DottedDict.from_base_and_override(self.init_options, override.get("initializationOptions")),
            settings=DottedDict.from_base_and_override(self.settings, override.get("settings")),
            env=override.get("env", self.env),
            experimental_capabilities=override.get(
                "experimental_capabilities", self.experimental_capabilities)
        )

    def resolve(self, variables: Dict[str, str]) -> ResolvedStartupConfig:
        tcp_port = None  # type: Optional[int]
        listener_socket = None  # type: Optional[socket.socket]
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
        for var, value in self.env.items():
            env[var] = sublime.expand_variables(value, variables)
        init_options = DottedDict(sublime.expand_variables(self.init_options.get(), variables))
        return ResolvedStartupConfig(command, tcp_port, init_options, env, listener_socket)

    def set_view_status(self, view: sublime.View, message: str) -> None:
        if sublime.load_settings("LSP.sublime-settings").get("show_view_status"):
            status = "{}: {}".format(self.name, message) if message else self.name
            view.set_status(self.status_key, status)

    def erase_view_status(self, view: sublime.View) -> None:
        view.erase_status(self.status_key)

    def match_view(self, view: sublime.View) -> bool:
        syntax = view.syntax()
        if syntax:
            # Every part of a x.y.z scope seems to contribute 8.
            # An empty selector result in a score of 1.
            # A non-matching non-empty selector results in a score of 0.
            # We want to match at least one part of an x.y.z, and we don't want to match on empty selectors.
            return sublime.score_selector(syntax.scope, self.selector) >= 8
        return False

    def __repr__(self) -> str:
        items = []  # type: List[str]
        for k, v in self.__dict__.items():
            if not k.startswith("_"):
                items.append("{}={}".format(k, repr(v)))
        return "{}({})".format(self.__class__.__name__, ", ".join(items))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ClientConfig):
            return False
        for k, v in self.__dict__.items():
            if not k.startswith("_") and v != getattr(other, k):
                return False
        return True


def syntax2scope(syntax_path: str) -> Optional[str]:
    syntax = sublime.syntax_from_path(syntax_path)
    return syntax.scope if syntax else None


def view2scope(view: sublime.View) -> str:
    try:
        return view.scope_name(0).split()[0]
    except IndexError:
        return ''


def _read_selector(config: Union[sublime.Settings, Dict[str, Any]]) -> str:
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
            language_id = config.get("languageId")
            if isinstance(language_id, str):
                selectors.append("source.{}".format(language_id))
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
        return "source.{}".format(language_id)
    return ""


def _read_priority_selector(config: Union[sublime.Settings, Dict[str, Any]]) -> str:
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
                selectors.append("source.{}".format(language_id))
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
        return "source.{}".format(language_id)
    return ""


def _find_free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def _start_tcp_listener(tcp_port: Optional[int]) -> socket.socket:
    sock = socket.socket()
    sock.bind(('localhost', tcp_port or 0))
    sock.settimeout(TCP_CONNECT_TIMEOUT)
    sock.listen(1)
    return sock
