from .code_actions import actions_manager
from .code_actions import CodeActionsByConfigName
from .completion import LspResolveDocsCommand
from .core.logging import debug
from .core.promise import Promise
from .core.protocol import CompletionItem
from .core.protocol import CompletionList
from .core.protocol import Diagnostic
from .core.protocol import DiagnosticSeverity
from .core.protocol import DocumentHighlightKind
from .core.protocol import Error
from .core.protocol import Range
from .core.protocol import Request
from .core.protocol import SignatureHelp
from .core.registry import best_session
from .core.registry import windows
from .core.sessions import Session
from .core.settings import userprefs
from .core.signature_help import SigHelp
from .core.types import basescope2languageid
from .core.types import debounced
from .core.types import FEATURES_TIMEOUT
from .core.types import SettingsRegistration
from .core.typing import Any, Callable, Optional, Dict, Generator, Iterable, List, Tuple, Union, cast
from .core.url import parse_uri
from .core.url import view_to_uri
from .core.views import DIAGNOSTIC_SEVERITY
from .core.views import diagnostic_severity
from .core.views import document_color_params
from .core.views import first_selection_region
from .core.views import format_completion
from .core.views import lsp_color_to_phantom
from .core.views import make_command_link
from .core.views import range_to_region
from .core.views import show_lsp_popup
from .core.views import text_document_identifier
from .core.views import text_document_position_params
from .core.views import update_lsp_popup
from .core.windows import AbstractViewListener
from .core.windows import WindowManager
from .semantic import get_semantic_scope_from_modifier
from .session_buffer import SessionBuffer
from .session_view import SessionView
from functools import partial
from weakref import WeakSet
from weakref import WeakValueDictionary
import itertools
import sublime
import sublime_plugin
import textwrap
import weakref
import webbrowser

SUBLIME_WORD_MASK = 515

_kind2name = {
    DocumentHighlightKind.Text: "text",
    DocumentHighlightKind.Read: "read",
    DocumentHighlightKind.Write: "write"
}

_kind2scope = {
    DocumentHighlightKind.Text: "region.bluish markup.highlight.text.lsp",
    DocumentHighlightKind.Read: "region.greenish markup.highlight.read.lsp",
    DocumentHighlightKind.Write: "region.yellowish markup.highlight.write.lsp"
}

Flags = int
ResolveCompletionsFn = Callable[[List[sublime.CompletionItem], Flags], None]

SessionName = str
CompletionResponse = Union[List[CompletionItem], CompletionList, None]
ResolvedCompletions = Tuple[Union[CompletionResponse, Error], SessionName]


def is_regular_view(v: sublime.View) -> bool:
    # Not from the quick panel (CTRL+P), and not a special view like a console, output panel or find-in-files panels.
    return not v.sheet().is_transient() and v.element() is None


def previous_non_whitespace_char(view: sublime.View, pt: int) -> str:
    prev = view.substr(pt - 1)
    if prev.isspace():
        return view.substr(view.find_by_class(pt, False, ~0) - 1)
    return prev


class TextChangeListener(sublime_plugin.TextChangeListener):

    ids_to_listeners = WeakValueDictionary()  # type: WeakValueDictionary[int, TextChangeListener]

    @classmethod
    def is_applicable(cls, buffer: sublime.Buffer) -> bool:
        v = buffer.primary_view()
        return v is not None and is_regular_view(v)

    def __init__(self) -> None:
        super().__init__()
        self.view_listeners = WeakSet()  # type: WeakSet[DocumentSyncListener]

    def attach(self, buffer: sublime.Buffer) -> None:
        super().attach(buffer)
        self.ids_to_listeners[self.buffer.buffer_id] = self

    def detach(self) -> None:
        self.ids_to_listeners.pop(self.buffer.buffer_id, None)
        super().detach()

    def on_text_changed(self, changes: Iterable[sublime.TextChange]) -> None:
        view = self.buffer.primary_view()
        if not view:
            return
        change_count = view.change_count()
        frozen_listeners = WeakSet(self.view_listeners)

        def notify() -> None:
            for listener in list(frozen_listeners):
                listener.on_text_changed_async(change_count, changes)

        sublime.set_timeout_async(notify)

    def on_reload_async(self) -> None:
        for listener in list(self.view_listeners):
            listener.reload_async()

    def on_revert_async(self) -> None:
        for listener in list(self.view_listeners):
            listener.revert_async()

    def __repr__(self) -> str:
        return "TextChangeListener({})".format(self.buffer.buffer_id)


class DocumentSyncListener(sublime_plugin.ViewEventListener, AbstractViewListener):

    CODE_ACTIONS_KEY = "lsp_code_action"
    ACTIVE_DIAGNOSTIC = "lsp_active_diagnostic"
    code_actions_debounce_time = FEATURES_TIMEOUT
    color_boxes_debounce_time = FEATURES_TIMEOUT
    highlights_debounce_time = FEATURES_TIMEOUT
    code_lenses_debounce_time = FEATURES_TIMEOUT
    code_lenses_debounce_time = FEATURES_TIMEOUT + 2000
    semantic_tokens_debounce_time = FEATURES_TIMEOUT

    _uri = None  # type: str

    @classmethod
    def applies_to_primary_view_only(cls) -> bool:
        return False

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        weakself = weakref.ref(self)

        def on_change() -> None:
            nonlocal weakself
            this = weakself()
            if this is not None:
                this._on_settings_object_changed()

        self._current_syntax = None
        existing_uri = view.settings().get("lsp_uri")
        if isinstance(existing_uri, str):
            self._uri = existing_uri
        else:
            self.set_uri(view_to_uri(view))
        self._registration = SettingsRegistration(view.settings(), on_change=on_change)
        self._setup()

    def __del__(self) -> None:
        self._cleanup()

    def _setup(self) -> None:
        syntax = self.view.syntax()
        if syntax:
            self._language_id = basescope2languageid(syntax.scope)  # type: str
        else:
            debug("view", self.view.id(), "has no syntax")
            self._language_id = ""
        self._manager = None  # type: Optional[WindowManager]
        self._session_views = {}  # type: Dict[str, SessionView]
        self._stored_region = sublime.Region(-1, -1)
        self._color_phantoms = sublime.PhantomSet(self.view, "lsp_color")
        self._sighelp = None  # type: Optional[SigHelp]
        self._registered = False

    def _cleanup(self) -> None:
        settings = self.view.settings()
        triggers = settings.get("auto_complete_triggers") or []  # type: List[Dict[str, str]]
        triggers = [trigger for trigger in triggers if 'server' not in trigger]
        settings.set("auto_complete_triggers", triggers)
        self._stored_region = sublime.Region(-1, -1)
        self._color_phantoms.update([])
        self.view.erase_status(AbstractViewListener.TOTAL_ERRORS_AND_WARNINGS_STATUS_KEY)
        self._clear_highlight_regions()
        self._clear_session_views_async()

    def _reset(self) -> None:
        # Have to do this on the main thread, since __init__ and __del__ are invoked on the main thread too
        self._cleanup()
        self._setup()
        # But this has to run on the async thread again
        sublime.set_timeout_async(self.on_activated_async)

    # --- Implements AbstractViewListener ------------------------------------------------------------------------------

    def on_post_move_window_async(self) -> None:
        if self._registered and self._manager:
            new_window = self.view.window()
            if not new_window:
                return
            old_window = self._manager.window()
            if new_window.id() == old_window.id():
                return
            self._manager.unregister_listener_async(self)
            sublime.set_timeout(self._reset)

    def on_session_initialized_async(self, session: Session) -> None:
        assert not self.view.is_loading()
        added = False
        if session.config.name not in self._session_views:
            self._session_views[session.config.name] = SessionView(self, session, self._uri)
            buf = self.view.buffer()
            if buf:
                text_change_listener = TextChangeListener.ids_to_listeners.get(buf.buffer_id)
                if text_change_listener:
                    text_change_listener.view_listeners.add(self)
            self.view.settings().set("lsp_active", True)
            added = True
        if added:
            self._do_color_boxes_async()
            self._do_code_lenses_async()
            self._do_semantic_tokens_async()

    def on_session_shutdown_async(self, session: Session) -> None:
        removed_session = self._session_views.pop(session.config.name, None)
        if removed_session:
            if not self._session_views:
                self.view.settings().erase("lsp_active")
                self._registered = False
        else:
            # SessionView was likely not created for this config so remove status here.
            session.config.erase_view_status(self.view)

    def diagnostics_panel_contribution_async(self) -> List[Tuple[str, Optional[int], Optional[str], Optional[str]]]:
        result = []  # type: List[Tuple[str, Optional[int], Optional[str], Optional[str]]]
        # Sort by severity
        for severity in range(1, len(DIAGNOSTIC_SEVERITY) + 1):
            for sb in self.session_buffers_async():
                data = sb.data_per_severity.get((severity, False))
                if data:
                    result.extend(data.panel_contribution)
                data = sb.data_per_severity.get((severity, True))
                if data:
                    result.extend(data.panel_contribution)
        # sort the result by asc line number
        return sorted(result)

    def diagnostics_async(
        self
    ) -> Generator[Tuple[SessionBuffer, List[Tuple[Diagnostic, sublime.Region]]], None, None]:
        change_count = self.view.change_count()
        for sb in self.session_buffers_async():
            # do not provide stale diagnostics
            if sb.diagnostics_version == change_count:
                yield sb, sb.diagnostics

    def diagnostics_intersecting_region_async(
        self,
        region: sublime.Region
    ) -> Tuple[List[Tuple[SessionBuffer, List[Diagnostic]]], sublime.Region]:
        covering = sublime.Region(region.a, region.b)
        result = []  # type: List[Tuple[SessionBuffer, List[Diagnostic]]]
        for sb, diagnostics in self.diagnostics_async():
            intersections = []  # type: List[Diagnostic]
            for diagnostic, candidate in diagnostics:
                if region.intersects(candidate):
                    covering = covering.cover(candidate)
                    intersections.append(diagnostic)
            if intersections:
                result.append((sb, intersections))
        return result, covering

    def diagnostics_touching_point_async(
        self,
        pt: int,
        max_diagnostic_severity_level: int = DiagnosticSeverity.Hint
    ) -> Tuple[List[Tuple[SessionBuffer, List[Diagnostic]]], sublime.Region]:
        covering = sublime.Region(pt, pt)
        result = []  # type: List[Tuple[SessionBuffer, List[Diagnostic]]]
        for sb, diagnostics in self.diagnostics_async():
            intersections = []  # type: List[Diagnostic]
            for diagnostic, candidate in diagnostics:
                severity = diagnostic_severity(diagnostic)
                if severity > max_diagnostic_severity_level:
                    continue
                if candidate.contains(pt):
                    covering = covering.cover(candidate)
                    intersections.append(diagnostic)
            if intersections:
                result.append((sb, intersections))
        return result, covering

    def on_diagnostics_updated_async(self) -> None:
        self._clear_code_actions_annotation()
        if userprefs().show_code_actions:
            self._do_code_actions()
        self._update_diagnostic_in_status_bar_async()

    def _update_diagnostic_in_status_bar_async(self) -> None:
        if userprefs().show_diagnostics_in_view_status:
            r = self._stored_region
            if r is not None:
                session_buffer_diagnostics, _ = self.diagnostics_touching_point_async(
                    r.b, userprefs().show_diagnostics_severity_level)
                if session_buffer_diagnostics:
                    for _, diagnostics in session_buffer_diagnostics:
                        diag = next(iter(diagnostics), None)
                        if diag:
                            self.view.set_status(self.ACTIVE_DIAGNOSTIC, diag["message"])
                            return
        self.view.erase_status(self.ACTIVE_DIAGNOSTIC)

    def session_views_async(self) -> Generator[SessionView, None, None]:
        yield from self._session_views.values()

    def session_buffers_async(self) -> Generator[SessionBuffer, None, None]:
        for sv in self.session_views_async():
            yield sv.session_buffer

    def on_text_changed_async(self, change_count: int, changes: Iterable[sublime.TextChange]) -> None:
        different, current_region = self._update_stored_region_async()
        if self.view.is_primary():
            for sv in self.session_views_async():
                sv.on_text_changed_async(change_count, changes)
        if not different:
            return
        self._clear_highlight_regions()
        if userprefs().document_highlight_style:
            self._when_selection_remains_stable_async(self._do_highlights_async, current_region,
                                                      after_ms=self.highlights_debounce_time)
        self._when_selection_remains_stable_async(self._do_color_boxes_async, current_region,
                                                  after_ms=self.color_boxes_debounce_time)
        self.do_signature_help_async(manual=False)
        self._when_selection_remains_stable_async(self._do_code_lenses_async, current_region,
                                                  after_ms=self.code_lenses_debounce_time)

        self._when_selection_remains_stable_async(self._do_semantic_tokens_async, current_region,
                                                  after_ms=self.semantic_tokens_debounce_time)

    def get_uri(self) -> str:
        return self._uri

    def set_uri(self, new_uri: str) -> None:
        self._uri = new_uri
        self.view.settings().set("lsp_uri", self._uri)

    def get_language_id(self) -> str:
        return self._language_id

    # --- Callbacks from Sublime Text ----------------------------------------------------------------------------------

    def on_load_async(self) -> None:
        if not self._registered and is_regular_view(self.view):
            self._register_async()

    def on_activated_async(self) -> None:
        if not self._registered and not self.view.is_loading() and is_regular_view(self.view):
            self._register_async()

    def on_selection_modified_async(self) -> None:
        different, current_region = self._update_stored_region_async()
        if different:
            if not self._is_in_higlighted_region(current_region.b):
                self._clear_highlight_regions()
            if userprefs().document_highlight_style:
                self._when_selection_remains_stable_async(self._do_highlights_async, current_region,
                                                          after_ms=self.highlights_debounce_time)
            self._clear_code_actions_annotation()
            if userprefs().show_code_actions:
                self._when_selection_remains_stable_async(self._do_code_actions, current_region,
                                                          after_ms=self.code_actions_debounce_time)
            self._update_diagnostic_in_status_bar_async()
            self._resolve_visible_code_lenses_async()

    def on_post_save_async(self) -> None:
        # Re-determine the URI; this time it's guaranteed to be a file because ST can only save files to a real
        # filesystem.
        uri = view_to_uri(self.view)
        new_scheme, _ = parse_uri(uri)
        old_scheme, _ = parse_uri(self._uri)
        self.set_uri(uri)
        if new_scheme == old_scheme:
            # The URI scheme hasn't changed so the only thing we have to do is to inform the attached session views
            # about the new URI.
            if self.view.is_primary():
                for sv in self.session_views_async():
                    sv.on_post_save_async(self._uri)
        else:
            # The URI scheme has changed. This means we need to re-determine whether any language servers should
            # be attached to the view.
            sublime.set_timeout(self._reset)

    def on_close(self) -> None:
        if self._registered and self._manager:
            manager = self._manager
            sublime.set_timeout_async(lambda: manager.unregister_listener_async(self))
        self._clear_session_views_async()

    def on_query_context(self, key: str, operator: int, operand: Any, match_all: bool) -> bool:
        # You can filter key bindings by the precense of a provider,
        if key == "lsp.session_with_capability" and operator == sublime.OP_EQUAL and isinstance(operand, str):
            capabilities = [s.strip() for s in operand.split("|")]
            for capability in capabilities:
                if any(self.sessions_async(capability)):
                    return True
            return False
        # You can filter key bindings by the precense of a specific name of a configuration.
        elif key == "lsp.session_with_name" and operator == sublime.OP_EQUAL and isinstance(operand, str):
            return bool(self.session_by_name(operand))
        # You can check if there is at least one session attached to this view.
        elif key in ("lsp.sessions", "setting.lsp_active"):
            return bool(self._session_views)
        # Signature Help handling
        elif key == "lsp.signature_help":
            if not self.view.is_popup_visible():
                if operand == 0:
                    sublime.set_timeout_async(lambda: self.do_signature_help_async(manual=True))
                    return True
            elif self._sighelp and self._sighelp.has_multiple_signatures() and not self.view.is_auto_complete_visible():
                # We use the "operand" for the number -1 or +1. See the key bindings.
                self._sighelp.select_signature(operand)
                self._update_sighelp_popup(self._sighelp.render(self.view))
                return True  # We handled this keybinding.
        return False

    def on_hover(self, point: int, hover_zone: int) -> None:
        if hover_zone != sublime.HOVER_TEXT or self.view.is_popup_visible():
            return
        self.view.run_command("lsp_hover", {"point": point})

    def on_post_text_command(self, command_name: str, args: Optional[Dict[str, Any]]) -> None:
        if command_name in ("next_field", "prev_field") and args is None:
            sublime.set_timeout_async(lambda: self.do_signature_help_async(manual=True))
        if not self.view.is_popup_visible():
            return
        if command_name in ["hide_auto_complete", "move", "commit_completion"] or 'delete' in command_name:
            # hide the popup when `esc` or arrows are pressed pressed
            self.view.hide_popup()

    def on_query_completions(self, prefix: str, locations: List[int]) -> Optional[sublime.CompletionList]:

        def resolve(clist: sublime.CompletionList, items: List[sublime.CompletionItem], flags: int = 0) -> None:
            # Resolve on the main thread to prevent any sort of data race for _set_target (see sublime_plugin.py).
            sublime.set_timeout(lambda: clist.set_completions(items, flags))

        clist = sublime.CompletionList()
        sublime.set_timeout_async(lambda: self._on_query_completions_async(partial(resolve, clist), locations[0]))
        return clist

    # --- textDocument/signatureHelp -----------------------------------------------------------------------------------

    def do_signature_help_async(self, manual: bool) -> None:
        # NOTE: We take the beginning of the region to check the previous char (see last_char variable). This is for
        # when a language server inserts a snippet completion.
        pos = self._stored_region.a
        if pos == -1:
            return
        session = self.session_async("signatureHelpProvider", pos)
        if not session:
            return
        triggers = []  # type: List[str]
        if not manual:
            for sb in self.session_buffers_async():
                if session == sb.session:
                    triggers = sb.get_capability("signatureHelpProvider.triggerCharacters") or []
                    break
        if not manual and not triggers:
            return
        last_char = previous_non_whitespace_char(self.view, pos)
        if manual or last_char in triggers:
            self.purge_changes_async()
            params = text_document_position_params(self.view, pos)
            session.send_request_async(
                Request.signatureHelp(params, self.view), lambda resp: self._on_signature_help(resp, pos))
        else:
            # TODO: Refactor popup usage to a common class. We now have sigHelp, completionDocs, hover, and diags
            # all using a popup. Most of these systems assume they have exclusive access to a popup, while in
            # reality there is only one popup per view.
            self.view.hide_popup()
            self._sighelp = None

    def _on_signature_help(self, response: Optional[SignatureHelp], point: int) -> None:
        self._sighelp = SigHelp.from_lsp(response)
        if self._sighelp:
            content = self._sighelp.render(self.view)

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
        show_lsp_popup(
            self.view,
            content,
            flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY | sublime.COOPERATE_WITH_AUTO_COMPLETE,
            location=point,
            on_hide=self._on_sighelp_hide,
            on_navigate=self._on_sighelp_navigate)
        self._visible = True

    def _update_sighelp_popup(self, content: str) -> None:
        update_lsp_popup(self.view, content)

    def _on_sighelp_hide(self) -> None:
        self._visible = False

    def _on_sighelp_navigate(self, href: str) -> None:
        webbrowser.open_new_tab(href)

    # --- textDocument/codeAction --------------------------------------------------------------------------------------

    def _do_code_actions(self) -> None:
        diagnostics_by_config, covering = self.diagnostics_intersecting_async(self._stored_region)
        actions_manager.request_for_region_async(self.view, covering, diagnostics_by_config, self._on_code_actions)

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
        if userprefs().show_code_actions == 'bulb':
            scope = 'region.yellowish lightbulb.lsp'
            icon = 'Packages/LSP/icons/lightbulb.png'
        else:  # 'annotation'
            if action_count > 1:
                title = '{} code actions'.format(action_count)
            else:
                title = next(itertools.chain.from_iterable(responses.values()))['title']
                title = "<br>".join(textwrap.wrap(title, width=30))
            code_actions_link = make_command_link('lsp_code_actions', title, {"commands_by_config": responses})
            annotations = ["<div class=\"actions\" style=\"font-family:system\">{}</div>".format(code_actions_link)]
            annotation_color = self.view.style_for_scope("region.bluish markup.accent.codeaction.lsp")["foreground"]
        self.view.add_regions(self.CODE_ACTIONS_KEY, regions, scope, icon, flags, annotations, annotation_color)

    def _clear_code_actions_annotation(self) -> None:
        self.view.erase_regions(self.CODE_ACTIONS_KEY)

    # --- textDocument/documentColor -----------------------------------------------------------------------------------

    def _do_color_boxes_async(self) -> None:
        session = self.session_async("colorProvider")
        if session:
            session.send_request_async(
                Request.documentColor(document_color_params(self.view), self.view), self._on_color_boxes)

    def _on_color_boxes(self, response: Any) -> None:
        color_infos = response if response else []
        self._color_phantoms.update([lsp_color_to_phantom(self.view, color_info) for color_info in color_infos])

    # --- textDocument/codeLens ----------------------------------------------------------------------------------------

    def on_code_lens_capability_registered_async(self) -> None:
        self._do_code_lenses_async()

    def _do_code_lenses_async(self) -> None:
        session = self.session_async("codeLensProvider")
        if session and session.uses_plugin():
            for sv in self.session_views_async():
                if sv.session == session:
                    sv.start_code_lenses_async()

    def _resolve_visible_code_lenses_async(self) -> None:
        session = self.session_async("codeLensProvider")
        if session and session.uses_plugin():
            for sv in self.session_views_async():
                if sv.session == session:
                    sv.resolve_visible_code_lenses_async()

    # --- textDocument/documentHighlight -------------------------------------------------------------------------------

    def _highlights_key(self, kind: int, multiline: bool) -> str:
        return "lsp_highlight_{}{}".format(_kind2name[kind], "m" if multiline else "s")

    def _clear_highlight_regions(self) -> None:
        for kind in range(1, 4):
            self.view.erase_regions(self._highlights_key(kind, False))
            self.view.erase_regions(self._highlights_key(kind, True))

    def _is_in_higlighted_region(self, point: int) -> bool:
        for kind in range(1, 4):
            regions = itertools.chain(
                self.view.get_regions(self._highlights_key(kind, False)),
                self.view.get_regions(self._highlights_key(kind, True))
            )  # type: Iterable[sublime.Region]
            if any(region.contains(point) for region in regions):
                return True
        return False

    def _do_highlights_async(self) -> None:
        region = first_selection_region(self.view)
        if region is None:
            return
        point = region.b
        session = self.session_async("documentHighlightProvider", point)
        if session:
            params = text_document_position_params(self.view, point)
            request = Request.documentHighlight(params, self.view)
            session.send_request_async(request, self._on_highlights)

    def _on_highlights(self, response: Optional[List]) -> None:
        if not isinstance(response, list):
            response = []
        kind2regions = {}  # type: Dict[Tuple[int, bool], List[sublime.Region]]
        for highlight in response:
            r = range_to_region(Range.from_lsp(highlight["range"]), self.view)
            kind = highlight.get("kind", DocumentHighlightKind.Text)
            kind2regions.setdefault((kind, len(self.view.split_by_newlines(r)) > 1), []).append(r)

        def render_highlights_on_main_thread() -> None:
            self._clear_highlight_regions()
            flags_multi, flags_single = userprefs().document_highlight_style_region_flags()
            for tup, regions in kind2regions.items():
                if not regions:
                    continue
                kind, multiline = tup
                key = self._highlights_key(kind, multiline)
                flags = flags_multi if multiline else flags_single
                self.view.add_regions(key, regions, scope=_kind2scope[kind], flags=flags)

        sublime.set_timeout(render_highlights_on_main_thread)

    # --- textDocument/semanticTokens -------------------------------------------------------------------------------

    def _do_semantic_tokens_async(self) -> None:
        if ("background" not in self.view.style_for_scope("meta.semantic-token.lsp") or
                not userprefs().enable_semantic_tokens):
            return
        session = self.session_async("semanticTokensProvider")
        if session:
            semantic_tokens_legend = {}
            try:
                semantic_tokens_legend = cast(dict, session.get_capability('semanticTokensProvider'))
            except ValueError:
                # print('semantic highlighting capabilies not provided by the server!!!')
                return

            params = {"textDocument": text_document_identifier(self.view)}
            session.send_request_async(
                Request.semanticTokens(params, self.view),
                lambda response: self._on_semantic_tokens_async(response, semantic_tokens_legend['legend']))

    def _on_semantic_tokens_async(self, response: dict, semantic_tokens_legend: dict) -> None:
        regions = cast(dict, {})
        data = response['data']
        prev_row = None
        prev_col = None
        for x in range(0, len(data), 5):
            encoded_token = data[x:x+5]

            if prev_row is not None:
                if encoded_token[0] == 0:
                    encoded_token[1] += prev_col
                    encoded_token[0] = prev_row
                else:
                    encoded_token[0] += prev_row

            point1 = self.view.text_point(encoded_token[0], encoded_token[1])
            point2 = self.view.text_point(encoded_token[0], encoded_token[1]+encoded_token[2])
            my_region = sublime.Region(point1, point2)

            scope = get_semantic_scope_from_modifier(encoded_token, semantic_tokens_legend)

            try:
                regions[scope].append(my_region)
            except KeyError:
                regions[scope] = []
                regions[scope].append(my_region)

            prev_row = encoded_token[0]
            prev_col = encoded_token[1]

        region_keys = []
        for key, value in regions.items():
            if key:
                reg_key = key.split(', ')[0]  # in case of multiple modifiers, getting a _single modifier_ unique key
                if reg_key in region_keys:    # instead of a long _combined key_, to comply with init_region_keys()
                    for i in range(1, len(key.split(', ')) - 1):
                        if key.split(', ')[i] not in region_keys:
                            reg_key = key.split(', ')[i]
                            break
                region_keys.append(reg_key)
                self.view.add_regions(reg_key, value, 'meta.semantic-token.lsp ' + key, flags=sublime.DRAW_NO_OUTLINE)

    # --- textDocument/complete ----------------------------------------------------------------------------------------

    def _on_query_completions_async(self, resolve_completion_list: ResolveCompletionsFn, location: int) -> None:
        sessions = list(self.sessions_async('completionProvider'))
        if not sessions or not self.view.is_valid():
            resolve_completion_list([], 0)
            return
        self.purge_changes_async()
        completion_promises = []  # type: List[Promise[ResolvedCompletions]]
        for session in sessions:

            def completion_request() -> Promise[ResolvedCompletions]:
                return session.send_request_task(
                    Request.complete(text_document_position_params(self.view, location), self.view)
                ).then(lambda response: (response, session.config.name))

            completion_promises.append(completion_request())

        Promise.all(completion_promises).then(
            lambda responses: self._on_all_settled(responses, resolve_completion_list))

    def _on_all_settled(
        self,
        responses: List[ResolvedCompletions],
        resolve_completion_list: ResolveCompletionsFn
    ) -> None:
        LspResolveDocsCommand.completions = {}
        items = []  # type: List[sublime.CompletionItem]
        errors = []  # type: List[Error]
        flags = 0  # int
        prefs = userprefs()
        if prefs.inhibit_snippet_completions:
            flags |= sublime.INHIBIT_EXPLICIT_COMPLETIONS
        if prefs.inhibit_word_completions:
            flags |= sublime.INHIBIT_WORD_COMPLETIONS
        for response, session_name in responses:
            if isinstance(response, Error):
                errors.append(response)
                continue
            session = self.session_by_name(session_name)
            if not session:
                continue
            response_items = []  # type: List[CompletionItem]
            if isinstance(response, dict):
                response_items = response["items"] or []
                if response.get("isIncomplete", False):
                    flags |= sublime.DYNAMIC_COMPLETIONS
            elif isinstance(response, list):
                response_items = response
            response_items = sorted(response_items, key=lambda item: item.get("sortText") or item["label"])
            LspResolveDocsCommand.completions[session_name] = response_items
            can_resolve_completion_items = session.has_capability('completionProvider.resolveProvider')
            items.extend(
                format_completion(response_item, index, can_resolve_completion_items, session.config.name)
                for index, response_item in enumerate(response_items))
        if items:
            flags |= sublime.INHIBIT_REORDER
        if errors:
            error_messages = ", ".join(str(error) for error in errors)
            sublime.status_message('Completion error: {}'.format(error_messages))
        resolve_completion_list(items, flags)

    # --- Public utility methods ---------------------------------------------------------------------------------------

    def session_async(self, capability: str, point: Optional[int] = None) -> Optional[Session]:
        return best_session(self.view, self.sessions_async(capability), point)

    def sessions_async(self, capability: Optional[str] = None) -> Generator[Session, None, None]:
        for sb in self.session_buffers_async():
            if capability is None or sb.has_capability(capability):
                yield sb.session

    def session_by_name(self, name: Optional[str] = None) -> Optional[Session]:
        for sb in self.session_buffers_async():
            if sb.session.config.name == name:
                return sb.session
        return None

    def get_capability_async(self, session: Session, capability_path: str) -> Optional[Any]:
        for sv in self.session_views_async():
            if sv.session == session:
                return sv.get_capability_async(capability_path)
        return None

    def has_capability_async(self, session: Session, capability_path: str) -> bool:
        for sv in self.session_views_async():
            if sv.session == session:
                return sv.has_capability_async(capability_path)
        return False

    def purge_changes_async(self) -> None:
        for sv in self.session_views_async():
            sv.purge_changes_async()

    def trigger_on_pre_save_async(self) -> None:
        for sv in self.session_views_async():
            sv.on_pre_save_async()

    def sum_total_errors_and_warnings_async(self) -> Tuple[int, int]:
        errors = 0
        warnings = 0
        for sb in self.session_buffers_async():
            errors += sb.total_errors
            warnings += sb.total_warnings
        return errors, warnings

    def revert_async(self) -> None:
        if self.view.is_primary():
            for sv in self.session_views_async():
                sv.on_revert_async()

    def reload_async(self) -> None:
        if self.view.is_primary():
            for sv in self.session_views_async():
                sv.on_reload_async()

    # --- Private utility methods --------------------------------------------------------------------------------------

    def _when_selection_remains_stable_async(self, f: Callable[[], None], r: sublime.Region, after_ms: int) -> None:
        debounced(f, after_ms, lambda: self._stored_region == r, async_thread=True)

    def _register_async(self) -> None:
        buf = self.view.buffer()
        if not buf:
            debug("not tracking bufferless view", self.view.id())
            return
        text_change_listener = TextChangeListener.ids_to_listeners.get(buf.buffer_id)
        if not text_change_listener:
            debug("couldn't find a text change listener for", self)
            return
        self._registered = True
        if not self._manager:
            window = self.view.window()
            if not window:
                return
            self._manager = windows.lookup(window)
        self._manager.register_listener_async(self)
        views = buf.views()
        if not isinstance(views, list):
            debug("skipping clone checks for", self)
            return
        self_id = self.view.id()
        for view in views:
            view_id = view.id()
            if view_id == self_id:
                continue
            listeners = list(sublime_plugin.view_event_listeners[view_id])
            for listener in listeners:
                if isinstance(listener, DocumentSyncListener):
                    debug("also registering", listener)
                    listener.on_load_async()

    def _update_stored_region_async(self) -> Tuple[bool, sublime.Region]:
        """
        Stores the current first selection in a variable.
        Note that due to this function (supposedly) running in the async worker thread of ST, it can happen that the
        view is already closed. In that case it returns Region(-1, -1). It also returns that value if there's no first
        selection.

        :returns:   A tuple with two elements. The second element is the new region, the first element signals whether
                    the previous region was different from the newly stored region.
        """
        current_region = first_selection_region(self.view)
        if current_region is not None:
            if self._stored_region != current_region:
                self._stored_region = current_region
                return True, current_region
        return False, sublime.Region(-1, -1)

    def _clear_session_views_async(self) -> None:
        session_views = self._session_views

        def clear_async() -> None:
            nonlocal session_views
            session_views.clear()

        sublime.set_timeout_async(clear_async)

    def _on_settings_object_changed(self) -> None:
        new_syntax = self.view.settings().get("syntax")
        new_uri = self.view.settings().get("lsp_uri")
        something_changed = False
        if new_syntax != self._current_syntax:
            self._current_syntax = new_syntax
            something_changed = True
        if isinstance(new_uri, str) and new_uri != self._uri:
            self._uri = new_uri
            something_changed = True
        if something_changed:
            self._reset()

    def __repr__(self) -> str:
        return "ViewListener({})".format(self.view.id())
