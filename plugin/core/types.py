from .collections import DottedDict
from .logging import debug
from .typing import Optional, List, Dict, Generator, Callable
import contextlib
import functools
import sublime
import time


@contextlib.contextmanager
def runtime(token: str) -> Generator[None, None, None]:
    t = time.time()
    yield
    debug(token, "running time:", int((time.time() - t) * 1000000), "μs")


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


class Settings:

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
        self.diagnostics_delay_ms = 0
        self.diagnostics_additional_delay_auto_complete_ms = 0
        self.show_symbol_action_links = False
        self.show_references_in_quick_panel = False
        self.disabled_capabilities = []  # type: List[str]
        self.log_debug = False
        self.log_server = []  # type: List[str]
        self.log_stderr = False
        self.log_max_size = 8 * 1024
        self.lsp_format_on_save = False
        self.lsp_code_actions_on_save = {}  # type: Dict[str, bool]
        self.code_action_on_save_timeout_ms = 2000

    def show_diagnostics_panel_always(self) -> bool:
        return self.auto_show_diagnostics_panel == "always"

    def show_diagnostics_panel_on_save(self) -> bool:
        return self.auto_show_diagnostics_panel == "saved"

    def document_highlight_style_to_add_regions_flags(self) -> int:
        return _settings_style_to_add_regions_flag(self.document_highlight_style)

    def diagnostics_highlight_style_to_add_regions_flag(self) -> int:
        # TODO: Unused for now
        return _settings_style_to_add_regions_flag(self.diagnostics_highlight_style)


class ClientStates(object):
    STARTING = 0
    READY = 1
    STOPPING = 2


class LanguageConfig(object):

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


class ClientConfig(object):
    def __init__(self,
                 name: str,
                 binary_args: List[str],
                 languages: List[LanguageConfig],
                 tcp_port: Optional[int],
                 enabled: bool = True,
                 init_options: dict = dict(),
                 settings: DottedDict = DottedDict(),
                 env: dict = dict(),
                 tcp_host: Optional[str] = None,
                 tcp_mode: Optional[str] = None,
                 experimental_capabilities: dict = dict()) -> None:
        self.name = name
        self.binary_args = binary_args
        self.languages = languages
        self.tcp_port = tcp_port
        self.tcp_host = tcp_host
        self.tcp_mode = tcp_mode
        self.enabled = enabled
        self.init_options = init_options
        self.settings = settings
        self.env = env
        self.experimental_capabilities = experimental_capabilities
        self.status_key = "lsp_{}".format(self.name)

    def set_view_status(self, view: sublime.View, message: str) -> None:
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


def syntax2scope(syntax: str) -> Optional[str]:
    try:
        return next(filter(lambda d: d['path'] == syntax, sublime.list_syntaxes()))['scope']
    except StopIteration:
        return None


def view2scope(view: sublime.View) -> str:
    try:
        return view.scope_name(0).split()[0]
    except IndexError:
        return ''
