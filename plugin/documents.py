from .code_actions import actions_manager
from .code_actions import CodeActionsByConfigName
from .core.css import css
from .core.protocol import Diagnostic
from .core.protocol import DocumentHighlightKind
from .core.protocol import Range
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LSPViewEventListener
from .core.sessions import Session
from .core.settings import settings as global_settings
from .core.signature_help import create_signature_help
from .core.signature_help import SignatureHelp
from .core.types import debounced
from .core.typing import Any, Callable, Optional, Dict, Generator, Iterable, List, Tuple, Union
from .core.views import DIAGNOSTIC_SEVERITY
from .core.views import document_color_params
from .core.views import FORMAT_MARKUP_CONTENT
from .core.views import FORMAT_STRING
from .core.views import lsp_color_to_phantom
from .core.views import make_command_link
from .core.views import minihtml
from .core.views import range_to_region
from .core.views import region_to_range
from .core.views import text_document_position_params
from .core.windows import AbstractViewListener
from .diagnostics import filter_by_range
from .diagnostics import view_diagnostics
from .session_buffer import SessionBuffer
from .session_view import SessionView
from weakref import ref
import html
import mdpopups
import sublime
import sublime_plugin
import webbrowser


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


def previous_non_whitespace_char(view: sublime.View, pt: int) -> str:
    prev = view.substr(pt - 1)
    if prev.isspace():
        return view.substr(view.find_by_class(pt, False, ~0) - 1)
    return prev


class ColorSchemeScopeRenderer:
    def __init__(self, view: sublime.View) -> None:
        self._scope_styles = {}  # type: dict
        self._view = view
        for scope in ["entity.name.function", "variable.parameter", "punctuation"]:
            self._scope_styles[scope] = mdpopups.scope2style(view, scope)

    def function(self, content: str, escape: bool = True) -> str:
        return self._wrap_with_scope_style(content, "entity.name.function", escape=escape)

    def punctuation(self, content: str) -> str:
        return self._wrap_with_scope_style(content, "punctuation")

    def parameter(self, content: str, emphasize: bool = False) -> str:
        return self._wrap_with_scope_style(content, "variable.parameter", emphasize)

    def markup(self, content: Union[str, Dict[str, str]]) -> str:
        return minihtml(self._view, content, allowed_formats=FORMAT_STRING | FORMAT_MARKUP_CONTENT)

    def _wrap_with_scope_style(self, content: str, scope: str, emphasize: bool = False, escape: bool = True) -> str:
        color = self._scope_styles[scope]["color"]
        additional_styles = 'font-weight: bold; text-decoration: underline;' if emphasize else ''
        content = html.escape(content, quote=False) if escape else content
        return '<span style="color: {};{}">{}</span>'.format(color, additional_styles, content)


class TextChangeListener(sublime_plugin.TextChangeListener):
    def __init__(self, buffer: Any, listener: AbstractViewListener) -> None:
        super().__init__(buffer)
        self.listener = ref(listener)

    # Created to have symmetry with "attach". Weird naming in internal API...
    def detach(self) -> None:
        self.remove()

    def on_text_changed_async(self, changes: Iterable[sublime.TextChange]) -> None:
        listener = self.listener()
        if listener:
            listener.on_text_changed_async(changes)

    def on_reload_async(self) -> None:
        listener = self.listener()
        if listener:
            listener.on_reload_async()

    def on_revert_async(self) -> None:
        listener = self.listener()
        if listener:
            listener.on_revert_async()


class DocumentSyncListener(LSPViewEventListener, AbstractViewListener):

    CODE_ACTIONS_KEY = "lsp_code_action"
    ACTIVE_DIAGNOSTIC = "lsp_active_diagnostic"
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
        self._sighelp = None  # type: Optional[SignatureHelp]
        self._sighelp_renderer = ColorSchemeScopeRenderer(self.view)
        self._text_change_listener = TextChangeListener(self.view.buffer(), self)

    def __del__(self) -> None:
        self._stored_region = sublime.Region(-1, -1)
        self._color_phantoms.update([])
        self.view.erase_status(AbstractViewListener.TOTAL_ERRORS_AND_WARNINGS_STATUS_KEY)
        self._clear_session_views_async()
        self._clear_highlight_regions()

    # --- Implements AbstractViewListener ------------------------------------------------------------------------------

    def on_session_initialized_async(self, session: Session) -> None:
        assert not self.view.is_loading()
        added = False
        if session.config.name not in self._session_views:
            self._session_views[session.config.name] = SessionView(self, session)
            self.view.settings().set("lsp_active", True)
            added = True
        if added:
            if "colorProvider" not in global_settings.disabled_capabilities:
                self._do_color_boxes_async()
            if not self._text_change_listener.is_attached():
                self._text_change_listener.attach(self.view.buffer())

    def on_session_shutdown_async(self, session: Session) -> None:
        self._session_views.pop(session.config.name, None)
        if not self._session_views:
            self.view.settings().erase("lsp_active")
            self._text_change_listener.detach()

    def diagnostics_panel_contribution_async(self) -> List[str]:
        result = []  # type: List[str]
        # Sort by severity
        for severity in range(1, len(DIAGNOSTIC_SEVERITY) + 1):
            for sb in self.session_buffers_async():
                data = sb.data_per_severity.get(severity)
                if data:
                    result.extend(data.panel_contribution)
        return result

    def diagnostics_async(self) -> Dict[str, List[Diagnostic]]:
        result = {}  # type: Dict[str, List[Diagnostic]]
        for sv in self.session_views_async():
            result[sv.session.config.name] = sv.get_diagnostics_async()
        return result

    def update_diagnostic_in_status_bar_async(self) -> None:
        if global_settings.show_diagnostics_in_view_status:
            r = self._get_current_range_async()
            if r is not None:
                diags_by_config_name, _ = self.diagnostics_intersecting_range_async(r)
                if diags_by_config_name:
                    for diags in diags_by_config_name.values():
                        diag = next(iter(diags), None)
                        if diag:
                            self.view.set_status(self.ACTIVE_DIAGNOSTIC, diag.message)
                            return
        self.view.erase_status(self.ACTIVE_DIAGNOSTIC)

    def session_views_async(self) -> Generator[SessionView, None, None]:
        yield from self._session_views.values()

    def session_buffers_async(self) -> Generator[SessionBuffer, None, None]:
        for sv in self.session_views_async():
            yield sv.session_buffer

    def on_text_changed_async(self, changes: Iterable[sublime.TextChange]) -> None:
        different, current_region = self._update_stored_region_async()
        if self.view.is_primary():
            for sv in self.session_views_async():
                sv.on_text_changed_async(changes)
        if not different:
            return
        if "documentHighlight" not in global_settings.disabled_capabilities:
            self._clear_highlight_regions()
            self._when_selection_remains_stable_async(self._do_highlights, current_region,
                                                      after_ms=self.highlights_debounce_time)
        if "colorProvider" not in global_settings.disabled_capabilities:
            self._when_selection_remains_stable_async(self._do_color_boxes_async, current_region,
                                                      after_ms=self.color_boxes_debounce_time)
        if "signatureHelp" not in global_settings.disabled_capabilities:
            self._do_signature_help()

    def on_revert_async(self) -> None:
        if self.view.is_primary():
            for sv in self.session_views_async():
                sv.on_revert_async()

    def on_reload_async(self) -> None:
        if self.view.is_primary():
            for sv in self.session_views_async():
                sv.on_reload_async()

    # --- Callbacks from Sublime Text ----------------------------------------------------------------------------------

    def on_load_async(self) -> None:
        if self._is_regular_view():
            self._register_async()

    def on_activated_async(self) -> None:
        if self._is_regular_view() and not self.view.is_loading():
            self._register_async()

    def on_selection_modified_async(self) -> None:
        different, current_region = self._update_stored_region_async()
        if different:
            if "documentHighlight" not in global_settings.disabled_capabilities:
                if not self.is_in_higlighted_region(current_region.b):
                    self._clear_highlight_regions()
                    self._when_selection_remains_stable_async(self._do_highlights, current_region,
                                                              after_ms=self.highlights_debounce_time)
            self._clear_code_actions_annotation()
            self._when_selection_remains_stable_async(self._do_code_actions, current_region,
                                                      after_ms=self.code_actions_debounce_time)
            self.update_diagnostic_in_status_bar_async()

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
        elif key == "lsp.signature_help":
            if not self.view.is_popup_visible():
                if operand == 0:
                    sublime.set_timeout_async(self._do_signature_help)
                    return True
            elif self._sighelp and self._sighelp.has_multiple_signatures() and not self.view.is_auto_complete_visible():
                # We use the "operand" for the number -1 or +1. See the keybindings.
                self._sighelp.select_signature(operand)
                self._update_sighelp_popup(self._sighelp.build_popup_content(self._sighelp_renderer))
                return True  # We handled this keybinding.
        return False

    def on_hover(self, point: int, hover_zone: int) -> None:
        if (hover_zone != sublime.HOVER_TEXT
                or self.view.is_popup_visible()
                or "hover" in global_settings.disabled_capabilities):
            return
        self.view.run_command("lsp_hover", {"point": point})

    def on_post_text_command(self, command_name: str, args: Optional[Dict[str, Any]]) -> None:
        if command_name in ("next_field", "prev_field") and args is None:
            if "signatureHelp" not in global_settings.disabled_capabilities:
                sublime.set_timeout_async(self._do_signature_help)

    # --- textDocument/signatureHelp -----------------------------------------------------------------------------------

    def _do_signature_help(self) -> None:
        # NOTE: We take the beginning of the region to check the previous char (see last_char variable). This is for
        # when a language server inserts a snippet completion.
        pos = self._stored_region.a
        if pos == -1:
            return
        if not self.view.match_selector(pos, self.view.settings().get("auto_complete_selector") or ""):  # ???
            return
        session = self.session("signatureHelpProvider")
        if not session:
            return
        triggers = session.get_capability("signatureHelpProvider.triggerCharacters")
        if not triggers:
            return
        last_char = previous_non_whitespace_char(self.view, pos)
        if last_char in triggers:
            self.purge_changes_async()
            params = text_document_position_params(self.view, pos)
            session.send_request(Request.signatureHelp(params), lambda resp: self._on_signature_help(resp, pos))
        else:
            # TODO: Refactor popup usage to a common class. We now have sigHelp, completionDocs, hover, and diags
            # all using a popup. Most of these systems assume they have exclusive access to a popup, while in
            # reality there is only one popup per view.
            self.view.hide_popup()
            self._sighelp = None

    def _on_signature_help(self, response: Optional[Dict], point: int) -> None:
        self._sighelp = create_signature_help(response)
        if self._sighelp:
            content = self._sighelp.build_popup_content(self._sighelp_renderer)

            def render_sighelp_on_main_thread() -> None:
                if self.view.is_popup_visible():
                    self._update_sighelp_popup(content)
                else:
                    self._show_sighelp_popup(content, point)

            sublime.set_timeout(render_sighelp_on_main_thread)

    def _show_sighelp_popup(self, content: str, point: int) -> None:
        # TODO: There are a bunch of places in the code where we assume we have exclusive access to a popup. The reality
        # is that there is really only one popup per view. Refactor everything that interacts with the popup to a common
        # class.
        flags = 0
        flags |= sublime.HIDE_ON_MOUSE_MOVE_AWAY
        flags |= sublime.COOPERATE_WITH_AUTO_COMPLETE
        mdpopups.show_popup(self.view,
                            content,
                            css=css().popups,
                            md=True,
                            flags=flags,
                            location=point,
                            wrapper_class=css().popups_classname,
                            max_width=800,
                            on_hide=self._on_sighelp_hide,
                            on_navigate=self._on_sighelp_navigate)
        self._visible = True

    def _update_sighelp_popup(self, content: str) -> None:
        mdpopups.update_popup(self.view,
                              content,
                              css=css().popups,
                              md=True,
                              wrapper_class=css().popups_classname)

    def _on_sighelp_hide(self) -> None:
        self._visible = False

    def _on_sighelp_navigate(self, href: str) -> None:
        webbrowser.open_new_tab(href)

    # --- textDocument/codeAction --------------------------------------------------------------------------------------

    def _do_code_actions(self) -> None:
        stored_range = region_to_range(self.view, self._stored_region)
        diagnostics_by_config, extended_range = filter_by_range(view_diagnostics(self.view), stored_range)
        actions_manager.request_for_range(self.view, extended_range, diagnostics_by_config, self._on_code_actions)

    def _on_code_actions(self, responses: CodeActionsByConfigName) -> None:
        action_count = sum(map(len, responses.values()))
        if action_count == 0:
            return
        regions = [sublime.Region(self._stored_region.b, self._stored_region.a)]
        scope = ""
        icon = ""
        flags = sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE
        annotations = []
        annotation_color = ""
        if global_settings.show_code_actions == 'bulb':
            scope = 'markup.changed'
            icon = 'Packages/LSP/icons/lightbulb.png'
        else:  # 'annotation'
            suffix = 's' if action_count > 1 else ''
            code_actions_link = make_command_link('lsp_code_actions', '{} code action{}'.format(action_count, suffix))
            annotations = ["<div class=\"actions\">{}</div>".format(code_actions_link)]
            annotation_color = '#2196F3'
        self.view.add_regions(self.CODE_ACTIONS_KEY, regions, scope, icon, flags, annotations, annotation_color)

    def _clear_code_actions_annotation(self) -> None:
        self.view.erase_regions(self.CODE_ACTIONS_KEY)

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

    def is_in_higlighted_region(self, point: int) -> bool:
        for kind in global_settings.document_highlight_scopes.keys():
            regions = self.view.get_regions("lsp_highlight_{}".format(kind))
            for r in regions:
                if r.contains(point):
                    return True
        return False

    def _do_highlights(self) -> None:
        if not len(self.view.sel()):
            return
        point = self.view.sel()[0].b
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

    # --- Public utility methods ---------------------------------------------------------------------------------------

    def purge_changes_async(self) -> None:
        for sv in self.session_views_async():
            sv.purge_changes_async()

    def trigger_on_pre_save_async(self) -> None:
        for sv in self.session_views_async():
            sv.on_pre_save_async(self.view.file_name() or "")

    def diagnostics_intersecting_range_async(self, r: Range) -> Tuple[Dict[str, List[Diagnostic]], Range]:
        return filter_by_range(self.diagnostics_async(), r)

    def sum_total_errors_and_warnings_async(self) -> Tuple[int, int]:
        errors = 0
        warnings = 0
        for sb in self.session_buffers_async():
            errors += sb.total_errors
            warnings += sb.total_warnings
        return errors, warnings

    # --- Private utility methods --------------------------------------------------------------------------------------

    def _when_selection_remains_stable_async(self, f: Callable[[], None], r: sublime.Region, after_ms: int) -> None:
        debounced(f, after_ms, lambda: self._stored_region == r, async_thread=True)

    def _register_async(self) -> None:
        file_name = self.view.file_name()
        if file_name:
            self._file_name = file_name
            self.manager.register_listener_async(self)

    def _update_stored_region_async(self) -> Tuple[bool, sublime.Region]:
        """
        Stores the current first selection in a variable.
        Note that due to this function (supposedly) running in the async worker thread of ST, it can happen that the
        view is already closed. In that case it returns Region(-1, -1). It also returns that value if there's no first
        selection.

        :returns:   A tuple with two elements. The second element is the new region, the first element signals whether
                    the previous region was different from the newly stored region.
        """
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

    def _get_current_range_async(self) -> Optional[Range]:
        region = self._get_current_region_async()
        if region is None:
            return None
        return region_to_range(self.view, region)

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
