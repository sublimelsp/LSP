from .code_actions import actions_manager
from .code_actions import CodeActionsByConfigName
from .completion import LspResolveDocsCommand
from .core.logging import debug
from .core.protocol import CodeLens
from .core.protocol import Command
from .core.protocol import Diagnostic
from .core.protocol import DocumentHighlightKind
from .core.protocol import Notification
from .core.protocol import Range
from .core.protocol import Request
from .core.protocol import SignatureHelp
from .core.registry import best_session
from .core.registry import LspTextCommand
from .core.registry import windows
from .core.sessions import Session
from .core.settings import userprefs
from .core.signature_help import SigHelp
from .core.types import basescope2languageid
from .core.types import debounced
from .core.types import FEATURES_TIMEOUT
from .core.typing import Any, Callable, Optional, Dict, Generator, Iterable, List, Tuple, Union
from .core.views import DIAGNOSTIC_SEVERITY
from .core.views import document_color_params
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
from .session_buffer import SessionBuffer
from .session_view import SessionView
from functools import partial
from weakref import WeakSet
from weakref import WeakValueDictionary
import functools
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

ResolveCompletionsFn = Callable[[List[sublime.CompletionItem], int], None]


def is_regular_view(v: sublime.View) -> bool:
    # Not from the quick panel (CTRL+P), must have a filename on-disk, and not a special view like a console,
    # output panel or find-in-files panels.
    return not v.sheet().is_transient() and bool(v.file_name()) and v.element() is None


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
    CODE_LENS_KEY = "lsp_code_lens"
    ACTIVE_DIAGNOSTIC = "lsp_active_diagnostic"
    code_actions_debounce_time = FEATURES_TIMEOUT
    color_boxes_debounce_time = FEATURES_TIMEOUT
    highlights_debounce_time = FEATURES_TIMEOUT
    code_lenses_debounce_time = FEATURES_TIMEOUT + 2000

    @classmethod
    def applies_to_primary_view_only(cls) -> bool:
        return False

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._setup()

    def __del__(self) -> None:
        self._cleanup()

    def _setup(self) -> None:
        self._manager = None  # type: Optional[WindowManager]
        self._session_views = {}  # type: Dict[str, SessionView]
        self._stored_region = sublime.Region(-1, -1)
        self._color_phantoms = sublime.PhantomSet(self.view, "lsp_color")
        self._code_lenses = []  # type: List[Tuple[CodeLens, sublime.Region]]
        self._sighelp = None  # type: Optional[SigHelp]
        self._language_id = ""
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

    # --- Implements AbstractViewListener ------------------------------------------------------------------------------

    def on_pre_move_window_async(self) -> None:
        if self._registered and self._manager:
            self._manager.unregister_listener_async(self)
            self._registered = False
            self._manager = None
        self._cleanup()

    def on_post_move_window_async(self) -> None:
        self._setup()
        self.on_activated_async()

    def on_session_initialized_async(self, session: Session) -> None:
        assert not self.view.is_loading()
        added = False
        if session.config.name not in self._session_views:
            self._session_views[session.config.name] = SessionView(self, session)
            buf = self.view.buffer()
            if buf:
                text_change_listener = TextChangeListener.ids_to_listeners.get(buf.buffer_id)
                if text_change_listener:
                    text_change_listener.view_listeners.add(self)
            self.view.settings().set("lsp_active", True)
            added = True
        if added:
            if "colorProvider" not in userprefs().disabled_capabilities:
                self._do_color_boxes_async()
            if "codeLensProvider" not in userprefs().disabled_capabilities:
                self._do_code_lenses_async()

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
                data = sb.data_per_severity.get(severity)
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
        pt: int
    ) -> Tuple[List[Tuple[SessionBuffer, List[Diagnostic]]], sublime.Region]:
        covering = sublime.Region(pt, pt)
        result = []  # type: List[Tuple[SessionBuffer, List[Diagnostic]]]
        for sb, diagnostics in self.diagnostics_async():
            intersections = []  # type: List[Diagnostic]
            for diagnostic, candidate in diagnostics:
                if candidate.contains(pt):
                    covering = covering.cover(candidate)
                    intersections.append(diagnostic)
            if intersections:
                result.append((sb, intersections))
        return result, covering

    def on_diagnostics_updated_async(self) -> None:
        self._clear_code_actions_annotation()
        self._do_code_actions()
        self._update_diagnostic_in_status_bar_async()

    def _update_diagnostic_in_status_bar_async(self) -> None:
        if userprefs().show_diagnostics_in_view_status:
            r = self._stored_region
            if r is not None:
                session_buffer_diagnostics, _ = self.diagnostics_touching_point_async(r.b)
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
        if "documentHighlight" not in userprefs().disabled_capabilities:
            self._clear_highlight_regions()
            self._when_selection_remains_stable_async(self._do_highlights_async, current_region,
                                                      after_ms=self.highlights_debounce_time)
        if "colorProvider" not in userprefs().disabled_capabilities:
            self._when_selection_remains_stable_async(self._do_color_boxes_async, current_region,
                                                      after_ms=self.color_boxes_debounce_time)
        if "signatureHelp" not in userprefs().disabled_capabilities:
            self.do_signature_help_async(manual=False)
        if "codeLensProvider" not in userprefs().disabled_capabilities:
            self._when_selection_remains_stable_async(self._do_code_lenses_async, current_region,
                                                      after_ms=self.code_lenses_debounce_time)

    def get_language_id(self) -> str:
        return self._language_id

    def get_resolved_code_lenses_for_region(self, region: sublime.Region) -> Generator[CodeLens, None, None]:
        region = self.view.line(region)
        for code_lens in self._code_lenses:
            if "command" in code_lens[0] and code_lens[1].intersects(region):
                yield code_lens[0]

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
            if "documentHighlight" not in userprefs().disabled_capabilities:
                if not self._is_in_higlighted_region(current_region.b):
                    self._clear_highlight_regions()
                self._when_selection_remains_stable_async(self._do_highlights_async, current_region,
                                                          after_ms=self.highlights_debounce_time)
            self._clear_code_actions_annotation()
            self._when_selection_remains_stable_async(self._do_code_actions, current_region,
                                                      after_ms=self.code_actions_debounce_time)
            self._update_diagnostic_in_status_bar_async()
            self._resolve_visible_code_lenses_async()

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
                    sublime.set_timeout_async(lambda: self.do_signature_help_async(manual=True))
                    return True
            elif self._sighelp and self._sighelp.has_multiple_signatures() and not self.view.is_auto_complete_visible():
                # We use the "operand" for the number -1 or +1. See the keybindings.
                self._sighelp.select_signature(operand)
                self._update_sighelp_popup(self._sighelp.render(self.view))
                return True  # We handled this keybinding.
        return False

    def on_hover(self, point: int, hover_zone: int) -> None:
        if (hover_zone != sublime.HOVER_TEXT
                or self.view.is_popup_visible()
                or "hover" in userprefs().disabled_capabilities):
            return
        self.view.run_command("lsp_hover", {"point": point})

    def on_post_text_command(self, command_name: str, args: Optional[Dict[str, Any]]) -> None:
        if command_name in ("next_field", "prev_field") and args is None:
            if "signatureHelp" not in userprefs().disabled_capabilities:
                sublime.set_timeout_async(lambda: self.do_signature_help_async(manual=True))
        if not self.view.is_popup_visible():
            return
        if command_name in ["hide_auto_complete", "move", "commit_completion"] or 'delete' in command_name:
            # hide the popup when `esc` or arrows are pressed pressed
            self.view.hide_popup()

    def on_query_completions(self, prefix: str, locations: List[int]) -> Optional[sublime.CompletionList]:
        if "completion" in userprefs().disabled_capabilities:
            return None

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
        session = self.session("signatureHelpProvider", pos)
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
            session.send_request_async(
                Request.documentColor(document_color_params(self.view), self.view), self._on_color_boxes)

    def _on_color_boxes(self, response: Any) -> None:
        color_infos = response if response else []
        self._color_phantoms.update([lsp_color_to_phantom(self.view, color_info) for color_info in color_infos])

    # --- textDocument/codeLens ----------------------------------------------------------------------------------------

    def on_code_lens_capability_registered_async(self) -> None:
        self._do_code_lenses_async()

    def _code_lens_key(self, index: int) -> str:
        return self.CODE_LENS_KEY + str(index)

    def _render_code_lens(self, name: str, index: int, region: sublime.Region, command: Optional[Command]) -> None:
        if command is not None:
            command_name = command.get("command")
            if command_name:
                annotation = make_command_link("lsp_execute", command["title"], {
                    "session_name": name,
                    "command_name": command_name,
                    "command_args": command.get("arguments")
                })
            else:
                annotation = command["title"]
        else:
            annotation = "..."
        annotation = '<div class="codelens">{}</div>'.format(annotation)
        accent = self.view.style_for_scope("region.greenish markup.codelens.accent")["foreground"]
        self.view.add_regions(self._code_lens_key(index), [region], "", "", 0, [annotation], accent)

    def _do_code_lenses_async(self) -> None:
        session = self.session("codeLensProvider")
        if session and session.uses_plugin():
            params = {"textDocument": text_document_identifier(self.view)}
            for sv in self.session_views_async():
                if sv.session == session:
                    for request_id, request in sv.active_requests.items():
                        if request.method == "codeAction/resolve":
                            session.send_notification(Notification("$/cancelRequest", {"id": request_id}))
            name = session.config.name
            session.send_request_async(
                Request("textDocument/codeLens", params, self.view),
                lambda r: self._on_code_lenses_async(name, r))

    def _on_code_lenses_async(self, name: str, response: Optional[List[CodeLens]]) -> None:
        for i in range(0, len(self._code_lenses)):
            self.view.erase_regions(self._code_lens_key(i))
        self._code_lenses.clear()
        if not isinstance(response, list):
            return
        for index, c in enumerate(response):
            region = range_to_region(Range.from_lsp(c["range"]), self.view)
            self._code_lenses.append((c, region))
            if "command" in c:
                # We consider a code lens that has a command to be already resolved.
                self._on_resolved_code_lens_async(name, index, region, c)
            else:
                self._render_code_lens(name, index, region, None)
        self._code_lenses = list((c, range_to_region(Range.from_lsp(c["range"]), self.view)) for c in response)
        self._resolve_visible_code_lenses_async()

    def _resolve_visible_code_lenses_async(self) -> None:
        session = self.session("codeLensProvider")
        if session:
            for index, code_lens, region in self._unresolved_code_lenses(self.view.visible_region()):
                callback = functools.partial(self._on_resolved_code_lens_async, session.config.name, index, region)
                session.send_request_async(Request("codeLens/resolve", code_lens, self.view), callback)

    def _on_resolved_code_lens_async(self, name: str, index: int, region: sublime.Region, code_lens: CodeLens) -> None:
        code_lens["session_name"] = name
        try:
            self._code_lenses[index] = (code_lens, region)
        except IndexError:
            return
        self._render_code_lens(name, index, region, code_lens["command"])

    def _unresolved_code_lenses(
        self,
        visible: sublime.Region
    ) -> Generator[Tuple[int, CodeLens, sublime.Region], None, None]:
        for index, tup in enumerate(self._code_lenses):
            code_lens, region = tup
            if not code_lens.get("command") and visible.intersects(region):
                yield index, code_lens, region

    # --- textDocument/documentHighlight -------------------------------------------------------------------------------

    def _clear_highlight_regions(self) -> None:
        for kind in userprefs().document_highlight_scopes.keys():
            self.view.erase_regions("lsp_highlight_{}".format(kind))

    def _is_in_higlighted_region(self, point: int) -> bool:
        for kind in userprefs().document_highlight_scopes.keys():
            regions = self.view.get_regions("lsp_highlight_{}".format(kind))
            for r in regions:
                if r.contains(point):
                    return True
        return False

    def _do_highlights_async(self) -> None:
        if not len(self.view.sel()):
            return
        point = self.view.sel()[0].b
        session = self.session("documentHighlightProvider", point)
        if session:
            params = text_document_position_params(self.view, point)
            request = Request.documentHighlight(params, self.view)
            session.send_request_async(request, self._on_highlights)

    def _on_highlights(self, response: Optional[List]) -> None:
        if not response:
            self._clear_highlight_regions()
            return
        kind2regions = {}  # type: Dict[str, List[sublime.Region]]
        for kind in range(0, 4):
            kind2regions[_kind2name[kind]] = []
        for highlight in response:
            r = range_to_region(Range.from_lsp(highlight["range"]), self.view)
            kind = highlight.get("kind", DocumentHighlightKind.Unknown)
            if kind is not None:
                kind2regions[_kind2name[kind]].append(r)

        def render_highlights_on_main_thread() -> None:
            self._clear_highlight_regions()
            flags = userprefs().document_highlight_style_to_add_regions_flags()
            for kind_str, regions in kind2regions.items():
                if regions:
                    scope = userprefs().document_highlight_scopes.get(kind_str, None)
                    if scope:
                        self.view.add_regions("lsp_highlight_{}".format(kind_str), regions, scope=scope, flags=flags)

        sublime.set_timeout(render_highlights_on_main_thread)

    # --- textDocument/complete ----------------------------------------------------------------------------------------

    def _on_query_completions_async(self, resolve: ResolveCompletionsFn, location: int) -> None:
        session = self.session('completionProvider', location)
        if not session:
            resolve([], 0)
            return
        self.purge_changes_async()
        can_resolve_completion_items = bool(session.get_capability('completionProvider.resolveProvider'))
        config_name = session.config.name
        session.send_request_async(
            Request.complete(text_document_position_params(self.view, location), self.view),
            lambda res: self._on_complete_result(res, resolve, can_resolve_completion_items, config_name),
            lambda res: self._on_complete_error(res, resolve))

    def _on_complete_result(self, response: Optional[Union[dict, List]], resolve: ResolveCompletionsFn,
                            can_resolve_completion_items: bool, session_name: str) -> None:
        response_items = []  # type: List[Dict]
        flags = 0
        prefs = userprefs()
        if prefs.inhibit_snippet_completions:
            flags |= sublime.INHIBIT_EXPLICIT_COMPLETIONS
        if prefs.inhibit_word_completions:
            flags |= sublime.INHIBIT_WORD_COMPLETIONS
        if isinstance(response, dict):
            response_items = response["items"] or []
            if response.get("isIncomplete", False):
                flags |= sublime.DYNAMIC_COMPLETIONS
        elif isinstance(response, list):
            response_items = response
        response_items = sorted(response_items, key=lambda item: item.get("sortText") or item["label"])
        LspResolveDocsCommand.completions = response_items
        items = [format_completion(response_item, index, can_resolve_completion_items, session_name)
                 for index, response_item in enumerate(response_items)]
        if items:
            flags |= sublime.INHIBIT_REORDER
        resolve(items, flags)

    def _on_complete_error(self, error: dict, resolve: ResolveCompletionsFn) -> None:
        resolve([], 0)
        LspResolveDocsCommand.completions = []
        sublime.status_message('Completion error: ' + str(error.get('message')))

    # --- Public utility methods ---------------------------------------------------------------------------------------

    @property
    def manager(self) -> WindowManager:  # TODO: Return type is an Optional[WindowManager] !
        if not self._manager:
            window = self.view.window()
            if window:
                self._manager = windows.lookup(window)
        return self._manager  # type: ignore

    def sessions(self, capability: Optional[str]) -> Generator[Session, None, None]:
        for sb in self.session_buffers_async():
            if capability is None or sb.has_capability(capability):
                yield sb.session

    def session(self, capability: str, point: Optional[int] = None) -> Optional[Session]:
        return best_session(self.view, self.sessions(capability), point)

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
            sv.on_pre_save_async(self.view.file_name() or "")

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
        syntax = self.view.syntax()
        if not syntax:
            debug("view", self.view.id(), "has no syntax")
            return
        self._language_id = basescope2languageid(syntax.scope)
        buf = self.view.buffer()
        if not buf:
            debug("not tracking bufferless view", self.view.id())
            return
        text_change_listener = TextChangeListener.ids_to_listeners.get(buf.buffer_id)
        if not text_change_listener:
            debug("couldn't find a text change listener for", self)
            return
        self._registered = True
        self.manager.register_listener_async(self)
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

    def _clear_session_views_async(self) -> None:
        session_views = self._session_views

        def clear_async() -> None:
            nonlocal session_views
            session_views.clear()

        sublime.set_timeout_async(clear_async)

    def __repr__(self) -> str:
        return "ViewListener({})".format(self.view.id())


class LspCodeLensCommand(LspTextCommand):

    def run(self, edit: sublime.Edit) -> None:
        listener = windows.listener_for_view(self.view)
        if not listener:
            return
        code_lenses = []  # type: List[CodeLens]
        for region in self.view.sel():
            code_lenses.extend(listener.get_resolved_code_lenses_for_region(region))
        if not code_lenses:
            return
        elif len(code_lenses) == 1:
            command = code_lenses[0]["command"]
            assert command
            args = {
                "session_name": code_lenses[0]["session_name"],
                "command_name": command["command"],
                "command_args": command["arguments"]
            }
            self.view.run_command("lsp_execute", args)
        else:
            self.view.show_popup_menu(
                [c["command"]["title"] for c in code_lenses],  # type: ignore
                lambda i: self.on_select(code_lenses, i)
            )

    def on_select(self, code_lenses: List[CodeLens], index: int) -> None:
        try:
            code_lens = code_lenses[index]
        except IndexError:
            return
        command = code_lens["command"]
        assert command
        args = {
            "session_name": code_lens["session_name"],
            "command_name": command["command"],
            "command_args": command["arguments"]
        }
        self.view.run_command("lsp_execute", args)
