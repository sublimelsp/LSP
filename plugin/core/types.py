from .collections import DottedDict
from .logging import debug
from .protocol import TextDocumentSyncKindNone
from .typing import Any, Optional, List, Dict, Generator, Callable, Iterable, Union, Set, TypeVar, Tuple
from threading import RLock
from wcmatch.glob import BRACE
from wcmatch.glob import globmatch
from wcmatch.glob import GLOBSTAR
import contextlib
import functools
import sublime
import time


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

    __slots__ = ("language", "scheme", "pattern", "selector", "feature_selector")

    def __init__(
        self,
        language: Optional[str] = None,
        scheme: Optional[str] = None,
        pattern: Optional[str] = None,
        feature_selector: str = ""
    ) -> None:
        self.language = language
        self.scheme = scheme
        self.pattern = pattern
        self.feature_selector = feature_selector
        if language:
            # This the connection between Language IDs and ST selectors.
            lang_id_map = sublime.load_settings("language-ids.sublime-settings")
            self.selector = lang_id_map.get(language, "source.{}".format(language))  # type: Optional[str]
        else:
            self.selector = None

    def matches(self, view: sublime.View) -> bool:
        """Does this filter match the view? An empty filter matches any view."""
        if self.selector:
            if not view.match_selector(0, self.selector):
                return False
        if self.scheme:
            # Can be "file" or "untitled"?
            pass
        if self.pattern:
            if not globmatch(view.file_name() or "", self.pattern, flags=GLOBSTAR | BRACE):
                return False
        return True

    def score_feature(self, view: sublime.View, pt: int) -> int:
        return view.score_selector(pt, self.feature_selector)


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
        return any(f.matches(view) for f in self.filters) if self.filters else True


class LanguageConfig:

    __slots__ = ('id', 'document_selector', 'feature_selector')

    def __init__(
        self,
        language_id: str,
        document_selector: Optional[str] = None,
        feature_selector: Optional[str] = None
    ) -> None:
        self.id = language_id
        self.document_selector = document_selector if document_selector else "source.{}".format(self.id)
        self.feature_selector = feature_selector if feature_selector else self.document_selector

    @functools.lru_cache(None)
    def score_document(self, scope: str) -> int:
        return sublime.score_selector(scope, self.document_selector)

    def score_feature(self, scope: str) -> int:
        return sublime.score_selector(scope, self.feature_selector)

    def match_scope(self, scope: str) -> bool:
        # Every part of a x.y.z scope seems to contribute 8.
        # An empty selector result in a score of 1.
        # A non-matching non-empty selector results in a score of 0.
        # We want to match at least one part of an x.y.z, and we don't want to match on empty selectors.
        return self.score_document(scope) >= 8

    def __repr__(self) -> str:
        return "{}(language_id={}, document_selector={}, feature_selector={})".format(
            self.__class__.__name__, repr(self.id), repr(self.document_selector), repr(self.feature_selector))


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


class ClientConfig:
    def __init__(self,
                 name: str,
                 languages: List[LanguageConfig],  # replace with DocumentSelector?
                 command: Optional[List[str]] = None,
                 binary_args: Optional[List[str]] = None,  # DEPRECATED
                 tcp_port: Optional[int] = None,
                 enabled: bool = True,
                 init_options: DottedDict = DottedDict(),
                 settings: DottedDict = DottedDict(),
                 env: Dict[str, str] = {},
                 experimental_capabilities: Optional[Dict[str, Any]] = None) -> None:
        self.name = name
        if isinstance(command, list):
            self.command = command
        else:
            assert isinstance(binary_args, list)
            self.command = binary_args
        self.languages = languages
        self.tcp_port = tcp_port
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
            command=read_list_setting(s, "command", []),
            languages=_read_language_configs(s),
            tcp_port=s.get("tcp_port"),
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
            command=d.get("command", []),
            languages=_read_language_configs(d),
            tcp_port=d.get("tcp_port"),
            enabled=d.get("enabled", False),
            init_options=DottedDict(d.get("initializationOptions")),
            settings=DottedDict(d.get("settings")),
            env=d.get("env", dict()),
            experimental_capabilities=d.get("experimental_capabilities", dict())
        )

    def update(self, override: Dict[str, Any]) -> "ClientConfig":
        languages = _read_language_configs(override)
        if not languages:
            languages = self.languages
        return ClientConfig(
            name=self.name,
            command=override.get("command", self.command),
            languages=languages,
            tcp_port=override.get("tcp_port", self.tcp_port),
            enabled=override.get("enabled", self.enabled),
            init_options=DottedDict.from_base_and_override(self.init_options, override.get("initializationOptions")),
            settings=DottedDict.from_base_and_override(self.settings, override.get("settings")),
            env=override.get("env", self.env),
            experimental_capabilities=override.get(
                "experimental_capabilities", self.experimental_capabilities)
        )

    def set_view_status(self, view: sublime.View, message: str) -> None:
        if sublime.load_settings("LSP.sublime-settings").get("show_view_status"):
            status = "{}: {}".format(self.name, message) if message else self.name
            view.set_status(self.status_key, status)

    def erase_view_status(self, view: sublime.View) -> None:
        view.erase_status(self.status_key)

    def match_scope(self, scope: str) -> bool:
        return any(language.match_scope(scope) for language in self.languages)

    def match_view(self, view: sublime.View) -> bool:
        return self.match_scope(view2scope(view))

    def score_feature(self, scope: str) -> int:
        highest_score = 0
        for language in self.languages:
            score = language.score_feature(scope)
            if score > highest_score:
                highest_score = score
        return highest_score

    def __repr__(self) -> str:
        items = []  # type: List[str]
        for k, v in self.__dict__.items():
            if not k.startswith("_"):
                items.append("{}={}".format(k, repr(getattr(self, k))))
        return "{}({})".format(self.__class__.__name__, ", ".join(items))


def syntax2scope(syntax_path: str) -> Optional[str]:
    syntax = sublime.syntax_from_path(syntax_path)
    return syntax.scope if syntax else None


def view2scope(view: sublime.View) -> str:
    try:
        return view.scope_name(0).split()[0]
    except IndexError:
        return ''


def _convert_syntaxes_to_selector(d: Union[sublime.Settings, Dict[str, Any]]) -> Optional[str]:
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


def _read_language_config(config: Union[sublime.Settings, Dict[str, Any]]) -> LanguageConfig:
    lang_id = config.get("languageId")
    if lang_id is None:
        # "languageId" must exist, just raise a KeyError if it doesn't exist.
        raise KeyError("languageId")
    document_selector = None  # type: Optional[str]
    feature_selector = None  # type: Optional[str]
    if _has(config, "syntaxes"):
        document_selector = _convert_syntaxes_to_selector(config)
        feature_selector = document_selector
    if _has(config, "document_selector"):
        # Overwrites potential old assignment to document_selector, which is OK.
        document_selector = config.get("document_selector")
    if _has(config, "feature_selector"):
        # Overwrites potential old assignment to feature_selector, which is OK.
        feature_selector = config.get("feature_selector")
    return LanguageConfig(language_id=lang_id, document_selector=document_selector, feature_selector=feature_selector)


def _read_language_configs(client_config: Union[sublime.Settings, Dict[str, Any]]) -> List[LanguageConfig]:
    languages = client_config.get("languages")
    if isinstance(languages, list):
        return list(map(_read_language_config, languages))
    if _has(client_config, "languageId"):
        return [_read_language_config(client_config)]
    return []
