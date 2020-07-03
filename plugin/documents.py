from .code_actions import actions_manager
from .code_actions import CodeActionsByConfigName
from .core.protocol import DocumentHighlightKind
from .core.protocol import Range
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LSPViewEventListener
from .core.sessions import Session
from .core.settings import settings as global_settings
from .core.types import debounced
from .core.typing import Any, Callable, Optional, Dict, Generator, Iterable, List, Tuple
from .core.views import document_color_params
from .core.views import lsp_color_to_phantom
from .core.views import make_link
from .core.views import range_to_region
from .core.views import region_to_range
from .core.views import text_document_position_params
from .core.windows import AbstractViewListener
from .diagnostics import filter_by_range
from .diagnostics import view_diagnostics
from .session_buffer import SessionBuffer
from .session_view import SessionView
import sublime


SUBLIME_WORD_MASK = 515

_kind2name = {
    DocumentHighlightKind.Unknown: "unknown",
    DocumentHighlightKind.Text: "text",
    DocumentHighlightKind.Read: "read",
    DocumentHighlightKind.Write: "write"
}


def is_at_word(view: sublime.View, event: Optional[dict]) -> bool:
    pos = get_position(view, event)
    return position_is_word(view, pos)


def position_is_word(view: sublime.View, position: int) -> bool:
    point_classification = view.classify(position)
    if point_classification & SUBLIME_WORD_MASK:
        return True
    else:
        return False


def is_transient_view(view: sublime.View) -> bool:
    window = view.window()
    if window:
        if window.get_view_index(view)[1] == -1:
            return True  # Quick panel transient views
        return view == window.transient_view_in_group(window.active_group())
    else:
        return True


class DocumentSyncListener(LSPViewEventListener, AbstractViewListener):

    ACTIONS_ANNOTATION_KEY = "lsp_action_annotations"
    code_actions_debounce_time = 800
    color_boxes_debounce_time = 500
    highlights_debounce_time = 500

    @classmethod
    def applies_to_primary_view_only(cls) -> bool:
        return False

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._session_views = {}  # type: Dict[str, SessionView]
        self._stored_region = sublime.Region(-1, -1)
        self._color_phantoms = sublime.PhantomSet(self.view, "lsp_color")

    def __del__(self) -> None:
        self._stored_region = sublime.Region(-1, -1)
        self._color_phantoms.update([])
        self._clear_highlight_regions()
        self._clear_session_views_async()

    # --- Implements AbstractViewListener ------------------------------------------------------------------------------

    def on_session_initialized_async(self, session: Session) -> None:
        assert not self.view.is_loading()
        added = False
        if session.config.name not in self._session_views:
            self._session_views[session.config.name] = SessionView(self, session)
            self.view.settings().set("lsp_active", True)
            added = True
        if added and "colorProvider" not in global_settings.disabled_capabilities:
            self._do_color_boxes_async()

    def on_session_shutdown_async(self, session: Session) -> None:
        self._session_views.pop(session.config.name, None)
        if not self._session_views:
            self.view.settings().erase("lsp_active")

    def session_views_async(self) -> Generator[SessionView, None, None]:
        yield from self._session_views.values()

    def session_buffers_async(self) -> Generator[SessionBuffer, None, None]:
        for sv in self.session_views_async():
            yield sv.session_buffer

    # --- Callbacks from Sublime Text ----------------------------------------------------------------------------------

    def on_load_async(self) -> None:
        if self._is_regular_view():
            self._register_async()

    def on_activated_async(self) -> None:
        if self._is_regular_view() and not self.view.is_loading():
            self._register_async()

    def on_modified_async(self) -> None:
        different, current_region = self._update_stored_region_async()
        if different:
            if "colorProvider" not in global_settings.disabled_capabilities:
                self._when_selection_remains_stable_async(self._do_color_boxes_async, current_region,
                                                          after_ms=self.color_boxes_debounce_time)

    def on_selection_modified_async(self) -> None:
        different, current_region = self._update_stored_region_async()
        if different:
            self._clear_highlight_regions()
            self._clear_code_actions_annotation()
            if "documentHighlight" not in global_settings.disabled_capabilities:
                self._when_selection_remains_stable_async(self._do_highlights, current_region,
                                                          after_ms=self.highlights_debounce_time)
            self._when_selection_remains_stable_async(self._do_code_actions, current_region,
                                                      after_ms=self.code_actions_debounce_time)

    def on_text_changed_async(self, changes: Iterable[sublime.TextChange]) -> None:
        if self.view.is_primary():
            for sv in self.session_views_async():
                sv.on_text_changed_async(changes)

    def on_revert_async(self) -> None:
        if self.view.is_primary():
            for sv in self.session_views_async():
                sv.on_revert_async()

    def on_reload_async(self) -> None:
        if self.view.is_primary():
            for sv in self.session_views_async():
                sv.on_reload_async()

    def on_post_save_async(self) -> None:
        if self.view.is_primary():
            for sv in self.session_views_async():
                sv.on_post_save_async()

    def on_close(self) -> None:
        self._clear_session_views_async()

    def on_query_context(self, key: str, operator: int, operand: Any, match_all: bool) -> bool:
        if key == "lsp.session_with_capability" and operator == sublime.OP_EQUAL and isinstance(operand, str):
            capabilities = [s.strip() for s in operand.split("|")]
            for capability in capabilities:
                if any(self.sessions(capability)):
                    return True
            return False
        elif key in ("lsp.sessions", "setting.lsp_active"):
            return bool(self._session_views)
        else:
            return False

    def on_hover(self, point: int, hover_zone: int) -> None:
        if (hover_zone != sublime.HOVER_TEXT
                or self.view.is_popup_visible()
                or "hover" in global_settings.disabled_capabilities):
            return
        self.view.run_command("lsp_hover", {"point": point})

    # --- textDocument/codeAction --------------------------------------------------------------------------------------

    def _do_code_actions(self) -> None:
        stored_range = region_to_range(self.view, self._stored_region)
        diagnostics_by_config, extended_range = filter_by_range(view_diagnostics(self.view), stored_range)
        actions_manager.request_for_range(self.view, extended_range, diagnostics_by_config, self._on_code_actions)

    def _on_code_actions(self, responses: CodeActionsByConfigName) -> None:
        action_count = sum(map(len, responses.values()))
        if action_count == 0:
            return
        suffix = 's' if action_count > 1 else ''
        code_actions_link = make_link('subl:lsp_code_actions', '{} code action{}'.format(action_count, suffix))
        self.view.add_regions(self.ACTIONS_ANNOTATION_KEY,
                              [sublime.Region(self._stored_region.b, self._stored_region.a)],
                              flags=sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE,
                              annotations=["<div class=\"actions\">{}</div>".format(code_actions_link)],
                              annotation_color='#2196F3')

    def _clear_code_actions_annotation(self) -> None:
        self.view.erase_regions(self.ACTIONS_ANNOTATION_KEY)

    # --- textDocument/documentColor -----------------------------------------------------------------------------------

    def _do_color_boxes_async(self) -> None:
        session = self.session("colorProvider")
        if session:
            session.send_request(Request.documentColor(document_color_params(self.view)), self._on_color_boxes)

    def _on_color_boxes(self, response: Any) -> None:
        color_infos = response if response else []
        self._color_phantoms.update([lsp_color_to_phantom(self.view, color_info) for color_info in color_infos])

    # --- textDocument/documentHighlight -------------------------------------------------------------------------------

    def _clear_highlight_regions(self) -> None:
        for kind in global_settings.document_highlight_scopes.keys():
            self.view.erase_regions("lsp_highlight_{}".format(kind))

    def _do_highlights(self) -> None:
        self._clear_highlight_regions()
        if len(self.view.sel()) != 1:
            return
        point = self.view.sel()[0].begin()
        session = self.session("documentHighlightProvider", point)
        if session:
            params = text_document_position_params(self.view, point)
            request = Request.documentHighlight(params)
            session.send_request(request, self._on_highlights)

    def _on_highlights(self, response: Optional[List]) -> None:
        if not response:
            return
        kind2regions = {}  # type: Dict[str, List[sublime.Region]]
        for kind in range(0, 4):
            kind2regions[_kind2name[kind]] = []
        for highlight in response:
            r = range_to_region(Range.from_lsp(highlight["range"]), self.view)
            kind = highlight.get("kind", DocumentHighlightKind.Unknown)
            if kind is not None:
                kind2regions[_kind2name[kind]].append(r)
        self._clear_highlight_regions()
        flags = global_settings.document_highlight_style_to_add_regions_flags()
        for kind_str, regions in kind2regions.items():
            if regions:
                scope = global_settings.document_highlight_scopes.get(kind_str, None)
                if scope:
                    self.view.add_regions("lsp_highlight_{}".format(kind_str), regions, scope=scope, flags=flags)

    # --- Utility methods ----------------------------------------------------------------------------------------------

    def purge_changes_async(self) -> None:
        for sv in self.session_views_async():
            sv.purge_changes_async()

    def trigger_on_pre_save_async(self) -> None:
        for sv in self.session_views_async():
            sv.on_pre_save_async(self.view.file_name() or "")

    def _when_selection_remains_stable_async(self, f: Callable[[], None], r: sublime.Region, after_ms: int) -> None:
        debounced(f, after_ms, lambda: self._stored_region == r, async_thread=True)

    def _register_async(self) -> None:
        file_name = self.view.file_name()
        if file_name:
            self._file_name = file_name
            self.manager.register_listener_async(self)

    def _update_stored_region_async(self) -> Tuple[bool, sublime.Region]:
        current_region = self._get_current_region_async()
        if current_region is not None:
            if self._stored_region != current_region:
                self._stored_region = current_region
                return True, current_region
        return False, sublime.Region(-1, -1)

    def _get_current_region_async(self) -> Optional[sublime.Region]:
        try:
            return self.view.sel()[0]
        except IndexError:
            return None

    def _is_regular_view(self) -> bool:
        v = self.view
        # Not from the quick panel (CTRL+P), must have a filename on-disk, and not a special view like a console,
        # output panel or find-in-files panels.
        return not is_transient_view(v) and bool(v.file_name()) and v.element() is None

    def _clear_session_views_async(self) -> None:
        session_views = self._session_views

        def clear_async() -> None:
            nonlocal session_views
            session_views.clear()

        sublime.set_timeout_async(clear_async)

    def __str__(self) -> str:
        return str(self.view.id())
