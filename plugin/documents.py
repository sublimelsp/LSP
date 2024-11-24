from __future__ import annotations
from .code_actions import actions_manager
from .code_actions import CodeActionOrCommand
from .code_actions import CodeActionsByConfigName
from .completion import QueryCompletionsTask
from .core.constants import DOCUMENT_HIGHLIGHT_KIND_NAMES
from .core.constants import DOCUMENT_HIGHLIGHT_KIND_SCOPES
from .core.constants import HOVER_ENABLED_KEY
from .core.constants import RegionKey
from .core.logging import debug
from .core.open import open_in_browser
from .core.panels import PanelName
from .core.protocol import Diagnostic
from .core.protocol import DiagnosticSeverity
from .core.protocol import DocumentHighlight
from .core.protocol import DocumentHighlightKind
from .core.protocol import DocumentHighlightParams
from .core.protocol import DocumentUri
from .core.protocol import FoldingRange
from .core.protocol import FoldingRangeParams
from .core.protocol import Request
from .core.protocol import SignatureHelp
from .core.protocol import SignatureHelpContext
from .core.protocol import SignatureHelpParams
from .core.protocol import SignatureHelpTriggerKind
from .core.registry import best_session
from .core.registry import get_position
from .core.registry import windows
from .core.sessions import AbstractViewListener
from .core.sessions import Session
from .core.sessions import SessionBufferProtocol
from .core.settings import userprefs
from .core.signature_help import SigHelp
from .core.types import basescope2languageid
from .core.types import ClientConfig
from .core.types import debounced
from .core.types import DebouncerNonThreadSafe
from .core.types import FEATURES_TIMEOUT
from .core.types import SettingsRegistration
from .core.url import parse_uri
from .core.url import view_to_uri
from .core.views import diagnostic_severity
from .core.views import first_selection_region
from .core.views import format_code_actions_for_quick_panel
from .core.views import format_diagnostic_for_html
from .core.views import make_link
from .core.views import MarkdownLangMap
from .core.views import range_to_region
from .core.views import show_lsp_popup
from .core.views import text_document_identifier
from .core.views import text_document_position_params
from .core.views import update_lsp_popup
from .core.windows import WindowManager
from .folding_range import folding_range_to_range
from .hover import code_actions_content
from .session_buffer import SessionBuffer
from .session_view import SessionView
from functools import partial
from functools import wraps
from os.path import basename
from typing import Any, Callable, Generator, Iterable, TypeVar
from typing import cast
from typing_extensions import Concatenate, ParamSpec
from weakref import WeakSet
from weakref import WeakValueDictionary
import itertools
import sublime
import sublime_plugin
import weakref
import webbrowser


P = ParamSpec('P')
R = TypeVar('R')


def requires_session(
    func: Callable[Concatenate[DocumentSyncListener, P], R]
) -> Callable[Concatenate[DocumentSyncListener, P], R | None]:
    """
    A decorator for the `DocumentSyncListener` event handlers, which immediately returns `None` if there are no
    `SessionView`s.
    """
    @wraps(func)
    def wrapper(self: DocumentSyncListener, *args: P.args, **kwargs: P.kwargs) -> R | None:
        if not self.session_views_async():
            return None
        return func(self, *args, **kwargs)
    return wrapper


def is_regular_view(v: sublime.View) -> bool:
    # Not from the quick panel (CTRL+P), and not a special view like a console, output panel or find-in-files panels.
    if v.element() is not None:
        return False
    if v.settings().get('is_widget'):
        return False
    # Not a syntax test file.
    if (filename := v.file_name()) and basename(filename).startswith('syntax_test_'):
        return False
    # Not a transient sheet (preview).
    sheet = v.sheet()
    if not sheet:
        return False
    if sheet.is_transient():
        return False
    return True


def previous_non_whitespace_char(view: sublime.View, pt: int) -> str:
    prev = view.substr(pt - 1)
    if prev.isspace():
        return view.substr(view.find_by_class(pt, False, ~0) - 1)  # type: ignore
    return prev


class TextChangeListener(sublime_plugin.TextChangeListener):

    ids_to_listeners: WeakValueDictionary[int, TextChangeListener] = WeakValueDictionary()

    @classmethod
    def is_applicable(cls, buffer: sublime.Buffer) -> bool:
        v = buffer.primary_view()
        return v is not None and is_regular_view(v)

    def __init__(self) -> None:
        super().__init__()
        self.view_listeners: WeakSet[DocumentSyncListener] = WeakSet()

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
        return f"TextChangeListener({self.buffer.buffer_id})"


class DocumentSyncListener(sublime_plugin.ViewEventListener, AbstractViewListener):

    ACTIVE_DIAGNOSTIC = "lsp_active_diagnostic"
    debounce_time = FEATURES_TIMEOUT
    color_boxes_debounce_time = FEATURES_TIMEOUT
    code_lenses_debounce_time = FEATURES_TIMEOUT

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

        self._uri = ''  # assumed to never be falsey
        self._current_syntax = self.view.settings().get("syntax")
        existing_uri = view.settings().get("lsp_uri")
        if isinstance(existing_uri, str):
            self._uri = existing_uri
        else:
            self.set_uri(view_to_uri(view))
        self._auto_complete_triggered_manually = False
        self._change_count_on_last_save = -1
        self._code_lenses_debouncer_async = DebouncerNonThreadSafe(async_thread=True)
        self._registration = SettingsRegistration(view.settings(), on_change=on_change)
        self._completions_task: QueryCompletionsTask | None = None
        self._stored_selection: list[sublime.Region] = []
        self._should_format_on_paste = False
        self.hover_provider_count = 0
        self._setup()

    def __del__(self) -> None:
        self._cleanup()

    def _setup(self) -> None:
        syntax = self.view.syntax()
        if syntax:
            self._language_id = basescope2languageid(syntax.scope)
        else:
            debug("view", self.view.id(), "has no syntax")
            self._language_id = ""
        self._manager: WindowManager | None = None
        self._session_views: dict[str, SessionView] = {}
        self._stored_selection = []
        self._sighelp: SigHelp | None = None
        self._lightbulb_line: int | None = None
        self._diagnostics_for_selection: list[tuple[SessionBufferProtocol, list[Diagnostic]]] = []
        self._code_actions_for_selection: list[CodeActionsByConfigName] = []
        self._registered = False

    def _cleanup(self) -> None:
        settings = self.view.settings()
        triggers: list[dict[str, str]] = settings.get("auto_complete_triggers") or []
        triggers = [trigger for trigger in triggers if 'server' not in trigger]
        settings.set("auto_complete_triggers", triggers)
        self._stored_selection = []
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
            old_window = self._manager.window
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
            self._do_code_lenses_async()

    def on_session_shutdown_async(self, session: Session) -> None:
        removed_session = self._session_views.pop(session.config.name, None)
        if removed_session:
            removed_session.on_before_remove()
            if not self._session_views:
                self.view.settings().erase("lsp_active")
                self._registered = False
        else:
            # SessionView was likely not created for this config so remove status here.
            session.config.erase_view_status(self.view)

    def _diagnostics_async(
        self, allow_stale: bool = False
    ) -> Generator[tuple[SessionBufferProtocol, list[tuple[Diagnostic, sublime.Region]]], None, None]:
        change_count = self.view.change_count()
        for sb in self.session_buffers_async():
            if sb.diagnostics_version == change_count or allow_stale:
                yield sb, sb.diagnostics

    def diagnostics_intersecting_region_async(
        self,
        region: sublime.Region
    ) -> tuple[list[tuple[SessionBufferProtocol, list[Diagnostic]]], sublime.Region]:
        covering = sublime.Region(region.begin(), region.end())
        result: list[tuple[SessionBufferProtocol, list[Diagnostic]]] = []
        for sb, diagnostics in self._diagnostics_async():
            intersections: list[Diagnostic] = []
            for diagnostic, candidate in diagnostics:
                # Checking against points is inclusive unlike checking whether region intersects another region
                # which is exclusive (at region end) and we want an inclusive behavior in this case.
                if region.intersects(candidate) or region.contains(candidate.a) or region.contains(candidate.b):
                    covering = covering.cover(candidate)
                    intersections.append(diagnostic)
            if intersections:
                result.append((sb, intersections))
        return result, covering

    def diagnostics_touching_point_async(
        self,
        pt: int,
        max_diagnostic_severity_level: int = DiagnosticSeverity.Hint
    ) -> tuple[list[tuple[SessionBufferProtocol, list[Diagnostic]]], sublime.Region]:
        covering = sublime.Region(pt, pt)
        result: list[tuple[SessionBufferProtocol, list[Diagnostic]]] = []
        for sb, diagnostics in self._diagnostics_async():
            intersections: list[Diagnostic] = []
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

    def on_diagnostics_updated_async(self, is_view_visible: bool) -> None:
        self._clear_code_actions_annotation()
        if is_view_visible and userprefs().show_code_actions:
            self._do_code_actions_async()
        self._update_diagnostic_in_status_bar_async()
        window = self.view.window()
        is_active_view = window and window.active_view() == self.view
        if is_active_view and self.view.change_count() == self._change_count_on_last_save:
            self._toggle_diagnostics_panel_if_needed_async()

    def _update_diagnostic_in_status_bar_async(self) -> None:
        if userprefs().show_diagnostics_in_view_status:
            if self._stored_selection:
                session_buffer_diagnostics, _ = self.diagnostics_touching_point_async(
                    self._stored_selection[0].b, userprefs().show_diagnostics_severity_level)
                if session_buffer_diagnostics:
                    for _, diagnostics in session_buffer_diagnostics:
                        diag = next(iter(diagnostics), None)
                        if diag:
                            self.view.set_status(self.ACTIVE_DIAGNOSTIC, diag["message"])
                            return
        self.view.erase_status(self.ACTIVE_DIAGNOSTIC)

    def session_buffers_async(self, capability: str | None = None) -> list[SessionBuffer]:
        return [
            sv.session_buffer for sv in self.session_views_async()
            if capability is None or sv.has_capability_async(capability)
        ]

    def session_views_async(self) -> list[SessionView]:
        return list(self._session_views.values())

    @requires_session
    def on_text_changed_async(self, change_count: int, changes: Iterable[sublime.TextChange]) -> None:
        if self.view.is_primary():
            for sv in self.session_views_async():
                sv.on_text_changed_async(change_count, changes)
        self._on_view_updated_async()

    def get_uri(self) -> DocumentUri:
        return self._uri

    def set_uri(self, new_uri: DocumentUri) -> None:
        self._uri = new_uri
        self.view.settings().set("lsp_uri", self._uri)

    def get_language_id(self) -> str:
        return self._language_id

    # --- Callbacks from Sublime Text ----------------------------------------------------------------------------------

    def on_load_async(self) -> None:
        if not self._registered and is_regular_view(self.view):
            self._register_async()
            return
        initially_folded_kinds = userprefs().initially_folded
        if initially_folded_kinds:
            session = self.session_async('foldingRangeProvider')
            if session:
                params: FoldingRangeParams = {'textDocument': text_document_identifier(self.view)}
                session.send_request_async(
                    Request.foldingRange(params, self.view),
                    partial(self._on_initial_folding_ranges, initially_folded_kinds))
        self.on_activated_async()

    def on_activated_async(self) -> None:
        if self.view.is_loading() or not is_regular_view(self.view):
            return
        if not self._registered:
            self._register_async()
        session_views = self.session_views_async()
        if not session_views:
            return
        if userprefs().show_code_actions:
            self._do_code_actions_async()
        for sv in session_views:
            if sv.code_lenses_needs_refresh:
                sv.set_code_lenses_pending_refresh(needs_refresh=False)
                sv.start_code_lenses_async()
        for sb in self.session_buffers_async():
            if sb.document_diagnostic_needs_refresh:
                sb.set_document_diagnostic_pending_refresh(needs_refresh=False)
                sb.do_document_diagnostic_async(self.view)
            if sb.semantic_tokens.needs_refresh:
                sb.set_semantic_tokens_pending_refresh(needs_refresh=False)
                sb.do_semantic_tokens_async(self.view)
            if sb.inlay_hints_needs_refresh:
                sb.set_inlay_hints_pending_refresh(needs_refresh=False)
                sb.do_inlay_hints_async(self.view)

    @requires_session
    def on_selection_modified_async(self) -> None:
        first_region, _ = self._update_stored_selection_async()
        if first_region is None:
            return
        if not self._is_in_higlighted_region(first_region.b):
            self._clear_highlight_regions()
        self._clear_code_actions_annotation()
        if userprefs().document_highlight_style or userprefs().show_code_actions:
            self._when_selection_remains_stable_async(
                self._on_selection_modified_debounced_async, first_region, after_ms=self.debounce_time)
        self._update_diagnostic_in_status_bar_async()
        self._resolve_visible_code_lenses_async()

    def _on_selection_modified_debounced_async(self) -> None:
        if userprefs().document_highlight_style:
            self._do_highlights_async()
        if userprefs().show_code_actions:
            self._do_code_actions_async()

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
        self._change_count_on_last_save = self.view.change_count()
        self._toggle_diagnostics_panel_if_needed_async()

    def _toggle_diagnostics_panel_if_needed_async(self) -> None:
        severity_threshold = userprefs().show_diagnostics_panel_on_save
        if severity_threshold == 0:
            return
        if not self._manager:
            return
        panel_manager = self._manager.panel_manager
        if not panel_manager:
            return
        has_relevant_diagnostcs = False
        for _, diagnostics in self._diagnostics_async(allow_stale=True):
            if any(diagnostic_severity(diagnostic) <= severity_threshold for diagnostic, _ in diagnostics):
                has_relevant_diagnostcs = True
                break
        if panel_manager.is_panel_open(PanelName.Diagnostics):
            if not has_relevant_diagnostcs:
                panel_manager.hide_diagnostics_panel_async()
        else:
            if has_relevant_diagnostcs:
                panel_manager.show_diagnostics_panel_async()

    def on_close(self) -> None:
        if self._registered and self._manager:
            manager = self._manager
            sublime.set_timeout_async(lambda: manager.unregister_listener_async(self))
        self._clear_session_views_async()

    def on_query_context(self, key: str, operator: int, operand: Any, match_all: bool) -> bool | None:
        # You can filter key bindings by the precense of a provider,
        if key == "lsp.session_with_capability" and operator == sublime.QueryOperator.EQUAL and \
                isinstance(operand, str):
            capabilities = [s.strip() for s in operand.split("|")]
            for capability in capabilities:
                if any(self.sessions_async(capability)):
                    return True
            return False
        # You can filter key bindings by the precense of a specific name of a configuration.
        elif key == "lsp.session_with_name" and operator == sublime.QueryOperator.EQUAL and isinstance(operand, str):
            return bool(self.session_by_name(operand))
        # You can check if there is at least one session attached to this view.
        elif key in ("lsp.sessions", "setting.lsp_active"):
            return bool(self._session_views)
        # Signature Help handling
        elif key == "lsp.signature_help_multiple_choices_available" and operator == sublime.QueryOperator.EQUAL:
            return operand == bool(
                self._sighelp and self._sighelp.has_multiple_signatures() and
                self.view.is_popup_visible() and not self.view.is_auto_complete_visible()
            )
        elif key == "lsp.signature_help_available" and operator == sublime.QueryOperator.EQUAL:
            return operand == bool(not self.view.is_popup_visible() and self._get_signature_help_session())
        elif key == "lsp.link_available" and operator == sublime.QueryOperator.EQUAL:
            position = get_position(self.view)
            if position is None:
                return not operand
            session = self.session_async('documentLinkProvider', position)
            if not session:
                return not operand
            session_view = session.session_view_for_view_async(self.view)
            if not session_view:
                return not operand
            return operand == bool(session_view.session_buffer.get_document_link_at_point(self.view, position))
        return None

    @requires_session
    def on_hover(self, point: int, hover_zone: int) -> None:
        if self.view.is_popup_visible():
            return
        window = self.view.window()
        if hover_zone == sublime.HoverZone.TEXT and window and window.settings().get(HOVER_ENABLED_KEY, True):
            self.view.run_command("lsp_hover", {"point": point})
        elif hover_zone == sublime.HoverZone.GUTTER:
            sublime.set_timeout_async(partial(self._on_hover_gutter_async, point))

    def _on_hover_gutter_async(self, point: int) -> None:
        content = ''
        if self._lightbulb_line == self.view.rowcol(point)[0]:
            content += code_actions_content(self._code_actions_for_selection)
        if userprefs().show_diagnostics_severity_level:
            diagnostics_with_config: list[tuple[ClientConfig, Diagnostic]] = []
            diagnostics_by_session_buffer: list[tuple[SessionBufferProtocol, list[Diagnostic]]] = []
            max_severity_level = min(userprefs().show_diagnostics_severity_level, DiagnosticSeverity.Information)
            if userprefs().diagnostics_gutter_marker:
                diagnostics_by_session_buffer = self.diagnostics_intersecting_async(self.view.line(point))[0]
            elif content:
                diagnostics_by_session_buffer = self._diagnostics_for_selection
            if content:
                max_severity_level = userprefs().show_diagnostics_severity_level
            for sb, diagnostics in diagnostics_by_session_buffer:
                diagnostics_with_config.extend(
                    (sb.session.config, diagnostic) for diagnostic in diagnostics
                    if diagnostic_severity(diagnostic) <= max_severity_level
                )
            if diagnostics_with_config:
                diagnostics_with_config.sort(key=lambda d: diagnostic_severity(d[1]))
                content += '<div class="diagnostics">'
                for config, diagnostic in diagnostics_with_config:
                    content += format_diagnostic_for_html(config, diagnostic)
                content += '</div>'
        if content:
            show_lsp_popup(
                self.view,
                content,
                flags=sublime.PopupFlags.HIDE_ON_MOUSE_MOVE_AWAY,
                location=point,
                on_navigate=lambda href: self._on_navigate(href, point))

    @requires_session
    def on_text_command(self, command_name: str, args: dict | None) -> tuple[str, dict] | None:
        if command_name == "auto_complete":
            self._auto_complete_triggered_manually = True
        elif command_name == "show_scope_name" and userprefs().semantic_highlighting:
            session = self.session_async("semanticTokensProvider")
            if session:
                return ("lsp_show_scope_name", {})
        elif command_name == 'paste_and_indent':
            # it is easier to find the region to format when `paste` is invoked,
            # so we intercept the `paste_and_indent` and replace it with the `paste` command.
            format_on_paste = self.view.settings().get('lsp_format_on_paste', userprefs().lsp_format_on_paste)
            if format_on_paste and self.session_async("documentRangeFormattingProvider"):
                return ('paste', {})
        return None

    @requires_session
    def on_post_text_command(self, command_name: str, args: dict[str, Any] | None) -> None:
        if command_name == 'paste':
            format_on_paste = self.view.settings().get('lsp_format_on_paste', userprefs().lsp_format_on_paste)
            if format_on_paste and self.session_async("documentRangeFormattingProvider"):
                self._should_format_on_paste = True
        elif command_name in ("next_field", "prev_field") and args is None:
            sublime.set_timeout_async(lambda: self.do_signature_help_async(manual=True))
        if not self.view.is_popup_visible():
            return
        if command_name in ("hide_auto_complete", "move", "commit_completion", "delete_word", "delete_to_mark",
                            "left_delete", "right_delete"):
            # hide the popup when `esc` or arrows are pressed
            self.view.hide_popup()

    @requires_session
    def on_query_completions(self, prefix: str, locations: list[int]) -> sublime.CompletionList | None:
        completion_list = sublime.CompletionList()
        triggered_manually = self._auto_complete_triggered_manually
        self._auto_complete_triggered_manually = False  # reset state for next completion popup
        sublime.set_timeout_async(
            lambda: self._on_query_completions_async(completion_list, locations[0], triggered_manually))
        return completion_list

    # --- textDocument/complete ----------------------------------------------------------------------------------------

    def _on_query_completions_async(
        self, clist: sublime.CompletionList, location: int, triggered_manually: bool
    ) -> None:
        if self._completions_task:
            self._completions_task.cancel_async()
        on_done = partial(self._on_query_completions_resolved_async, clist)
        self._completions_task = QueryCompletionsTask(self.view, location, triggered_manually, on_done)
        sessions = list(self.sessions_async('completionProvider'))
        if not sessions or not self.view.is_valid():
            self._completions_task.cancel_async()
            return
        self.purge_changes_async()
        self._completions_task.query_completions_async(sessions)

    def _on_query_completions_resolved_async(
        self,
        clist: sublime.CompletionList,
        completions: list[sublime.CompletionItem],
        flags: sublime.AutoCompleteFlags = sublime.AutoCompleteFlags.NONE
    ) -> None:
        self._completions_task = None
        # Resolve on the main thread to prevent any sort of data race for _set_target (see sublime_plugin.py).
        sublime.set_timeout(lambda: clist.set_completions(completions, flags))

    # --- textDocument/signatureHelp -----------------------------------------------------------------------------------

    def do_signature_help_async(self, manual: bool) -> None:
        session = self._get_signature_help_session()
        if not session or not self._stored_selection:
            return
        pos = self._stored_selection[0].a
        triggers: list[str] = []
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
            position_params = text_document_position_params(self.view, pos)
            trigger_kind = SignatureHelpTriggerKind.Invoked if manual else SignatureHelpTriggerKind.TriggerCharacter
            context_params: SignatureHelpContext = {
                'triggerKind': trigger_kind,
                'isRetrigger': self._sighelp is not None,
            }
            if not manual:
                context_params["triggerCharacter"] = last_char
            if self._sighelp:
                context_params["activeSignatureHelp"] = self._sighelp.active_signature_help()
            params: SignatureHelpParams = {
                "textDocument": position_params["textDocument"],
                "position": position_params["position"],
                "context": context_params
            }
            language_map = session.markdown_language_id_to_st_syntax_map()
            request = Request.signatureHelp(params, self.view)
            session.send_request_async(request, lambda resp: self._on_signature_help(resp, pos, language_map))
        elif self._sighelp:
            if self.view.match_selector(pos, "meta.function-call.arguments"):
                # Don't force close the signature help popup while the user is typing the parameters.
                # See also: https://github.com/sublimehq/sublime_text/issues/5518
                pass
            else:
                # TODO: Refactor popup usage to a common class. We now have sigHelp, completionDocs, hover, and diags
                # all using a popup. Most of these systems assume they have exclusive access to a popup, while in
                # reality there is only one popup per view.
                self.view.hide_popup()
                self._sighelp = None

    def _get_signature_help_session(self) -> Session | None:
        # NOTE: We take the beginning of the region to check the previous char (see last_char variable). This is for
        # when a language server inserts a snippet completion.
        if not self._stored_selection:
            return
        pos = self._stored_selection[0].a
        return self.session_async("signatureHelpProvider", pos)

    def _on_signature_help(
        self,
        response: SignatureHelp | None,
        point: int,
        language_map: MarkdownLangMap | None
    ) -> None:
        self._sighelp = SigHelp.from_lsp(response, language_map)
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
            flags=sublime.PopupFlags.COOPERATE_WITH_AUTO_COMPLETE,
            location=point,
            body_id='lsp-signature-help',
            on_hide=self._on_sighelp_hide,
            on_navigate=self._on_sighelp_navigate)

    def navigate_signature_help(self, forward: bool) -> None:
        if self._sighelp:
            self._sighelp.select_signature(forward)
            self._update_sighelp_popup(self._sighelp.render(self.view))

    def _update_sighelp_popup(self, content: str) -> None:
        update_lsp_popup(self.view, content)

    def _on_sighelp_hide(self) -> None:
        self._sighelp = None

    def _on_sighelp_navigate(self, href: str) -> None:
        webbrowser.open_new_tab(href)

    # --- textDocument/codeAction --------------------------------------------------------------------------------------

    def _do_code_actions_async(self) -> None:
        if not self._stored_selection:
            return
        self._diagnostics_for_selection, covering = self.diagnostics_intersecting_async(self._stored_selection[0])
        actions_manager \
            .request_for_region_async(self.view, covering, self._diagnostics_for_selection, manual=False) \
            .then(self._on_code_actions)

    def _on_code_actions(self, responses: list[CodeActionsByConfigName]) -> None:
        self._code_actions_for_selection = responses
        action_count = 0
        first_action_title = ''
        for _, actions in responses:
            count = len(actions)
            if count == 0:
                continue
            action_count += count
            if not first_action_title:
                first_action_title = actions[0]['title']
        if action_count == 0 or not self._stored_selection:
            return
        region = self._stored_selection[0]
        regions = [sublime.Region(region.b, region.a)]
        scope = ""
        icon = ""
        flags = sublime.RegionFlags.DRAW_NO_FILL | sublime.RegionFlags.DRAW_NO_OUTLINE | sublime.RegionFlags.NO_UNDO
        annotations = []
        annotation_color = ""
        if userprefs().show_code_actions == 'bulb':
            scope = 'region.yellowish lightbulb.lsp'
            icon = 'Packages/LSP/icons/lightbulb.png'
            self._lightbulb_line = self.view.rowcol(regions[0].begin())[0]
        else:  # 'annotation'
            title = f'{action_count} code actions' if action_count > 1 else first_action_title
            code_actions_link = make_link('code-actions:', title)
            annotations = [f"<div class=\"actions\" style=\"font-family:system\">{code_actions_link}</div>"]
            annotation_color = self.view.style_for_scope("region.bluish markup.accent.codeaction.lsp")["foreground"]
        self.view.add_regions(
            RegionKey.CODE_ACTION, regions, scope, icon, flags, annotations, annotation_color,
            on_navigate=self._on_code_actions_annotation_click
        )

    def _on_code_actions_annotation_click(self, href: str) -> None:
        if href == 'code-actions:' and self._code_actions_for_selection:
            self.view.run_command('lsp_code_actions', {'code_actions_by_config': self._code_actions_for_selection})

    def _clear_code_actions_annotation(self) -> None:
        self.view.erase_regions(RegionKey.CODE_ACTION)
        self._lightbulb_line = None

    def _on_navigate(self, href: str, point: int) -> None:
        if href.startswith('code-actions:'):
            _, config_name = href.split(":")
            actions = next(actions for name, actions in self._code_actions_for_selection if name == config_name)
            if len(actions) > 1:
                window = self.view.window()
                if window:
                    items, selected_index = format_code_actions_for_quick_panel(
                        map(lambda action: (config_name, action), actions))
                    window.show_quick_panel(
                        items,
                        lambda i: self.handle_code_action_select(config_name, actions, i),
                        selected_index=selected_index,
                        placeholder="Code actions")
            else:
                self.handle_code_action_select(config_name, actions, 0)
        else:
            open_in_browser(href)

    def handle_code_action_select(self, config_name: str, actions: list[CodeActionOrCommand], index: int) -> None:
        if index == -1:
            return

        def run_async() -> None:
            session = self.session_by_name(config_name)
            if session:
                session.run_code_action_async(actions[index], progress=True, view=self.view)

        sublime.set_timeout_async(run_async)

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

    def _highlights_key(self, kind: DocumentHighlightKind, multiline: bool) -> str:
        return "lsp_highlight_{}{}".format(DOCUMENT_HIGHLIGHT_KIND_NAMES[kind], "m" if multiline else "s")

    def _clear_highlight_regions(self) -> None:
        for kind in [DocumentHighlightKind.Text, DocumentHighlightKind.Read, DocumentHighlightKind.Write]:
            self.view.erase_regions(self._highlights_key(kind, False))
            self.view.erase_regions(self._highlights_key(kind, True))

    def _is_in_higlighted_region(self, point: int) -> bool:
        for kind in [DocumentHighlightKind.Text, DocumentHighlightKind.Read, DocumentHighlightKind.Write]:
            regions: Iterable[sublime.Region] = itertools.chain(
                self.view.get_regions(self._highlights_key(kind, False)),
                self.view.get_regions(self._highlights_key(kind, True))
            )
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
            params = cast(DocumentHighlightParams, text_document_position_params(self.view, point))
            request = Request.documentHighlight(params, self.view)
            session.send_request_async(request, self._on_highlights)

    def _on_highlights(self, response: list[DocumentHighlight] | None) -> None:
        if not isinstance(response, list):
            response = []
        kind2regions: dict[tuple[DocumentHighlightKind, bool], list[sublime.Region]] = {}
        for highlight in response:
            r = range_to_region(highlight["range"], self.view)
            multiline = len(self.view.split_by_newlines(r)) > 1
            if multiline and not userprefs().show_multiline_document_highlights:
                continue
            kind = highlight.get("kind", DocumentHighlightKind.Text)
            kind2regions.setdefault((kind, multiline), []).append(r)

        def render_highlights_on_main_thread() -> None:
            self._clear_highlight_regions()
            prefs = userprefs()
            flags_multi, flags_single = prefs.highlight_style_region_flags(prefs.document_highlight_style)
            for tup, regions in kind2regions.items():
                if not regions:
                    continue
                kind, multiline = tup
                key = self._highlights_key(kind, multiline)
                flags = flags_multi if multiline else flags_single
                self.view.add_regions(key, regions, scope=DOCUMENT_HIGHLIGHT_KIND_SCOPES[kind], flags=flags)

        sublime.set_timeout(render_highlights_on_main_thread)

    # --- textDocument/foldingRange ------------------------------------------------------------------------------------

    def _on_initial_folding_ranges(self, kinds: list[str], response: list[FoldingRange] | None) -> None:
        if not response:
            return
        regions = [
            range_to_region(folding_range_to_range(folding_range), self.view)
            for kind in kinds
            for folding_range in response if kind == folding_range.get('kind')
        ]
        if regions:
            self.view.fold(regions)

    # --- Public utility methods ---------------------------------------------------------------------------------------

    def session_async(self, capability: str, point: int | None = None) -> Session | None:
        return best_session(self.view, self.sessions_async(capability), point)

    def sessions_async(self, capability: str | None = None) -> list[Session]:
        return [
            sb.session for sb in self.session_buffers_async()
            if capability is None or sb.has_capability(capability)
        ]

    def session_by_name(self, name: str | None = None) -> Session | None:
        for sb in self.session_buffers_async():
            if sb.session.config.name == name:
                return sb.session
        return None

    def get_capability_async(self, session: Session, capability_path: str) -> Any | None:
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

    def revert_async(self) -> None:
        if self.view.is_primary():
            for sv in self.session_views_async():
                sv.on_revert_async()
        self._on_view_updated_async()

    def reload_async(self) -> None:
        if self.view.is_primary():
            for sv in self.session_views_async():
                sv.on_reload_async()
        self._on_view_updated_async()

    # --- Private utility methods --------------------------------------------------------------------------------------

    def _when_selection_remains_stable_async(self, f: Callable[[], None], r: sublime.Region, after_ms: int) -> None:
        debounced(f, after_ms, partial(self._is_selection_stable_async, r), async_thread=True)

    def _is_selection_stable_async(self, region: sublime.Region) -> bool:
        return bool(self._stored_selection and self._stored_selection[0] == region)

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
            self._manager = windows.lookup(self.view.window())
        if not self._manager:
            return
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
            listeners = list(sublime_plugin.view_event_listeners.get(view_id, []))
            for listener in listeners:
                if isinstance(listener, DocumentSyncListener):
                    debug("also registering", listener)
                    listener.on_load_async()

    def _on_view_updated_async(self) -> None:
        if self._should_format_on_paste:
            self._should_format_on_paste = False
            sublime.get_clipboard_async(self._format_on_paste_async)
        self._code_lenses_debouncer_async.debounce(
            self._do_code_lenses_async, timeout_ms=self.code_lenses_debounce_time)
        first_region, _ = self._update_stored_selection_async()
        if first_region is None:
            return
        self._clear_highlight_regions()
        if userprefs().document_highlight_style:
            self._when_selection_remains_stable_async(
                self._do_highlights_async, first_region, after_ms=self.debounce_time)
        self.do_signature_help_async(manual=False)

    def _update_stored_selection_async(self) -> tuple[sublime.Region | None, bool]:
        """
        Stores the current selection in a variable.
        Note that due to this function (supposedly) running in the async worker thread of ST, it can happen that the
        view is already closed. In that case it returns `None`. It also returns that value if there's no first
        selection.

        :returns:   A tuple with two elements. The first element returns the first selection region if it has changed.
                    The second element signals whether any selection region has changed.
        """
        selection = list(self.view.sel())
        if self._stored_selection == selection:
            return None, False
        changed_first_region = None
        if selection:
            stored_first_region = self._stored_selection[0] if self._stored_selection else None
            current_first_region = selection[0]
            if stored_first_region != current_first_region:
                changed_first_region = current_first_region
        self._stored_selection = selection
        return changed_first_region, True

    def _format_on_paste_async(self, clipboard_text: str) -> None:
        sel = self.view.sel()
        split_clipboard_text = clipboard_text.split('\n')
        multi_cursor_paste = len(split_clipboard_text) == len(sel) and len(sel) > 1
        original_selection = list(sel)
        regions_to_format: list[sublime.Region] = []
        pasted_text = clipboard_text
        # add regions to selection, in order for lsp_format_document_range to format those regions
        for index, region in enumerate(sel):
            if multi_cursor_paste:
                pasted_text = split_clipboard_text[index]
            pasted_region = self.view.find(
                pasted_text, region.end(), sublime.FindFlags.REVERSE | sublime.FindFlags.LITERAL)
            if pasted_region:
                # Including whitespace may help servers format a range better
                # More info at https://github.com/sublimelsp/LSP/pull/2311#issuecomment-1688593038
                a = self.view.find_by_class(
                    pasted_region.a,
                    False,
                    sublime.PointClassification.WORD_END | sublime.PointClassification.PUNCTUATION_END
                )
                formatting_region = sublime.Region(a, pasted_region.b)
                regions_to_format.append(formatting_region)
        self.purge_changes_async()

        def run_sync() -> None:
            sel.add_all(regions_to_format)
            self.view.run_command('lsp_format_document_range')
            sel.clear()
            sel.add_all(original_selection)

        sublime.set_timeout(run_sync)

    def _clear_session_views_async(self) -> None:
        session_views = self._session_views

        def clear_async() -> None:
            nonlocal session_views
            for session_view in session_views.values():
                session_view.on_before_remove()
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
        return f"ViewListener({self.view.id()})"
