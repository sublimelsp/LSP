from .core.protocol import Diagnostic
from .core.protocol import DiagnosticSeverity
from .core.protocol import DocumentLink
from .core.protocol import DocumentUri
from .core.protocol import InlayHintParams
from .core.protocol import InlayHintResponse
from .core.protocol import Range
from .core.protocol import Request
from .core.protocol import TextDocumentSyncKindFull
from .core.protocol import TextDocumentSyncKindNone
from .core.sessions import Session
from .core.sessions import SessionViewProtocol
from .core.settings import userprefs
from .core.types import Capabilities
from .core.types import debounced
from .core.types import Debouncer
from .core.types import FEATURES_TIMEOUT
from .core.typing import Any, Callable, Iterable, Optional, List, Set, Dict, Tuple
from .core.views import DIAGNOSTIC_SEVERITY
from .core.views import diagnostic_severity
from .core.views import did_change
from .core.views import did_close
from .core.views import did_open
from .core.views import did_save
from .core.views import document_color_params
from .core.views import DOCUMENT_LINK_FLAGS
from .core.views import entire_content_range
from .core.views import lsp_color_to_phantom
from .core.views import MissingUriError
from .core.views import range_to_region
from .core.views import region_to_range
from .core.views import text_document_identifier
from .core.views import will_save
from .inlay_hint import inlay_hint_to_phantom
from .semantic_highlighting import SemanticToken
from weakref import WeakSet
import sublime
import time


class PendingChanges:

    __slots__ = ('version', 'changes')

    def __init__(self, version: int, changes: Iterable[sublime.TextChange]) -> None:
        self.version = version
        self.changes = list(changes)

    def update(self, version: int, changes: Iterable[sublime.TextChange]) -> None:
        self.version = version
        self.changes.extend(changes)


class DiagnosticSeverityData:

    __slots__ = ('regions', 'regions_with_tag', 'annotations', 'scope', 'icon')

    def __init__(self, severity: int) -> None:
        self.regions = []  # type: List[sublime.Region]
        self.regions_with_tag = {}  # type: Dict[int, List[sublime.Region]]
        self.annotations = []  # type: List[str]
        _, _, self.scope, self.icon, _, _ = DIAGNOSTIC_SEVERITY[severity - 1]
        if userprefs().diagnostics_gutter_marker != "sign":
            self.icon = userprefs().diagnostics_gutter_marker


class SemanticTokensData:

    __slots__ = (
        'data', 'result_id', 'active_region_keys', 'tokens', 'view_change_count', 'needs_refresh', 'pending_response')

    def __init__(self) -> None:
        self.data = []  # type: List[int]
        self.result_id = None  # type: Optional[str]
        self.active_region_keys = set()  # type: Set[int]
        self.tokens = []  # type: List[SemanticToken]
        self.view_change_count = 0
        self.needs_refresh = False
        self.pending_response = None  # type: Optional[int]


class SessionBuffer:
    """
    Holds state per session per buffer.

    It stores the URI, handles document synchronization for the buffer, and stores/receives diagnostics for the
    buffer. The diagnostics are then published further to the views attached to this buffer. It also maintains the
    dynamically registered capabilities applicable to this particular buffer.
    """

    def __init__(self, session_view: SessionViewProtocol, buffer_id: int, uri: DocumentUri) -> None:
        view = session_view.view
        self.opened = False
        # Every SessionBuffer has its own personal capabilities due to "dynamic registration".
        self.capabilities = Capabilities()
        self._session = session_view.session
        self._session_views = WeakSet()  # type: WeakSet[SessionViewProtocol]
        self._session_views.add(session_view)
        self.last_known_uri = uri
        self.id = buffer_id
        self.pending_changes = None  # type: Optional[PendingChanges]
        self.diagnostics = []  # type: List[Tuple[Diagnostic, sublime.Region]]
        self.data_per_severity = {}  # type: Dict[Tuple[int, bool], DiagnosticSeverityData]
        self.diagnostics_version = -1
        self.diagnostics_flags = 0
        self.diagnostics_are_visible = False
        self.last_text_change_time = 0.0
        self.total_errors = 0
        self.total_warnings = 0
        self.should_show_diagnostics_panel = False
        self.diagnostics_debouncer = Debouncer()
        self.color_phantoms = sublime.PhantomSet(view, "lsp_color")
        self.document_links = []  # type: List[DocumentLink]
        self.semantic_tokens = SemanticTokensData()
        self._semantic_region_keys = {}  # type: Dict[str, int]
        self._last_semantic_region_key = 0
        self._inlay_hints_phantom_set = sublime.PhantomSet(view, "lsp_inlay_hints")
        self._check_did_open(view)
        self._session.register_session_buffer_async(self)

    def __del__(self) -> None:
        mgr = self.session.manager()
        if mgr:
            mgr.update_diagnostics_panel_async()
        self.color_phantoms.update([])
        # If the session is exiting then there's no point in sending textDocument/didClose and there's also no point
        # in unregistering ourselves from the session.
        if not self.session.exiting:
            # Only send textDocument/didClose when we are the only view left (i.e. there are no other clones).
            self._check_did_close()
            self.session.unregister_session_buffer_async(self)

    @property
    def session(self) -> Session:
        return self._session

    @property
    def session_views(self) -> 'WeakSet[SessionViewProtocol]':
        return self._session_views

    def _check_did_open(self, view: sublime.View) -> None:
        if not self.opened and self.should_notify_did_open():
            language_id = self.get_language_id()
            if not language_id:
                # we're closing
                return
            self.session.send_notification(did_open(view, language_id))
            self.opened = True
            self._do_color_boxes_async(view, view.change_count())
            self.do_semantic_tokens_async(view)
            self.do_inlay_hints_async(view)
            if userprefs().link_highlight_style in ("underline", "none"):
                self._do_document_link_async(view, view.change_count())
            self.session.notify_plugin_on_session_buffer_change(self)

    def _check_did_close(self) -> None:
        if self.opened and self.should_notify_did_close():
            self.session.send_notification(did_close(uri=self.last_known_uri))
            self.opened = False

    def get_uri(self) -> Optional[str]:
        for sv in self.session_views:
            return sv.get_uri()
        return None

    def get_language_id(self) -> Optional[str]:
        for sv in self.session_views:
            return sv.get_language_id()
        return None

    def get_view_in_group(self, group: int) -> sublime.View:
        for sv in self.session_views:
            view = sv.get_view_for_group(group)
            if view:
                return view
        return next(iter(self.session_views)).view

    @property
    def language_id(self) -> str:
        """
        Deprecated: use get_language_id
        """
        return self.get_language_id() or ""

    def add_session_view(self, sv: SessionViewProtocol) -> None:
        self.session_views.add(sv)

    def remove_session_view(self, sv: SessionViewProtocol) -> None:
        self._clear_semantic_token_regions(sv.view)
        self.session_views.remove(sv)

    def register_capability_async(
        self,
        registration_id: str,
        capability_path: str,
        registration_path: str,
        options: Dict[str, Any]
    ) -> None:
        self.capabilities.register(registration_id, capability_path, registration_path, options)
        view = None  # type: Optional[sublime.View]
        for sv in self.session_views:
            sv.on_capability_added_async(registration_id, capability_path, options)
            if view is None:
                view = sv.view
        if view is not None:
            if capability_path.startswith("textDocumentSync."):
                self._check_did_open(view)

    def unregister_capability_async(
        self,
        registration_id: str,
        capability_path: str,
        registration_path: str
    ) -> None:
        discarded = self.capabilities.unregister(registration_id, capability_path, registration_path)
        if discarded is None:
            return
        for sv in self.session_views:
            sv.on_capability_removed_async(registration_id, discarded)

    def get_capability(self, capability_path: str) -> Optional[Any]:
        if self.session.config.is_disabled_capability(capability_path):
            return None
        value = self.capabilities.get(capability_path)
        return value if value is not None else self.session.capabilities.get(capability_path)

    def has_capability(self, capability: str) -> bool:
        value = self.get_capability(capability)
        return value is not False and value is not None

    def text_sync_kind(self) -> int:
        value = self.capabilities.text_sync_kind()
        return value if value > TextDocumentSyncKindNone else self.session.text_sync_kind()

    def should_notify_did_open(self) -> bool:
        return self.capabilities.should_notify_did_open() or self.session.should_notify_did_open()

    def should_notify_will_save(self) -> bool:
        return self.capabilities.should_notify_will_save() or self.session.should_notify_will_save()

    def should_notify_did_save(self) -> Tuple[bool, bool]:
        do_it, include_text = self.capabilities.should_notify_did_save()
        return (do_it, include_text) if do_it else self.session.should_notify_did_save()

    def should_notify_did_close(self) -> bool:
        return self.capabilities.should_notify_did_close() or self.session.should_notify_did_close()

    def on_text_changed_async(self, view: sublime.View, change_count: int,
                              changes: Iterable[sublime.TextChange]) -> None:
        self.last_text_change_time = time.time()
        last_change = list(changes)[-1]
        if last_change.a.pt == 0 and last_change.b.pt == 0 and last_change.str == '' and view.size() != 0:
            # Issue https://github.com/sublimehq/sublime_text/issues/3323
            # A special situation when changes externally. We receive two changes,
            # one that removes all content and one that has 0,0,'' parameters.
            pass
        else:
            purge = False
            if self.pending_changes is None:
                self.pending_changes = PendingChanges(change_count, changes)
                purge = True
            elif self.pending_changes.version < change_count:
                self.pending_changes.update(change_count, changes)
                purge = True
            if purge:
                debounced(lambda: self.purge_changes_async(view), FEATURES_TIMEOUT,
                          lambda: view.is_valid() and change_count == view.change_count(), async_thread=True)

    def on_revert_async(self, view: sublime.View) -> None:
        self.pending_changes = None  # Don't bother with pending changes
        self.session.send_notification(did_change(view, view.change_count(), None))

    on_reload_async = on_revert_async

    def purge_changes_async(self, view: sublime.View) -> None:
        if self.pending_changes is not None:
            sync_kind = self.text_sync_kind()
            if sync_kind == TextDocumentSyncKindNone:
                return
            if sync_kind == TextDocumentSyncKindFull:
                changes = None
                version = view.change_count()
            else:
                changes = self.pending_changes.changes
                version = self.pending_changes.version
            try:
                notification = did_change(view, version, changes)
                self.session.send_notification(notification)
            except MissingUriError:
                return  # we're closing
            finally:
                self.pending_changes = None
            self._do_color_boxes_async(view, version)
            self.do_semantic_tokens_async(view)
            if userprefs().link_highlight_style in ("underline", "none"):
                self._do_document_link_async(view, version)
            self.do_inlay_hints_async(view)
            self.session.notify_plugin_on_session_buffer_change(self)

    def on_pre_save_async(self, view: sublime.View) -> None:
        if self.should_notify_will_save():
            self.purge_changes_async(view)
            # TextDocumentSaveReason.Manual
            self.session.send_notification(will_save(self.last_known_uri, 1))

    def on_post_save_async(self, view: sublime.View, new_uri: DocumentUri) -> None:
        if new_uri != self.last_known_uri:
            self._check_did_close()
            self.last_known_uri = new_uri
            self._check_did_open(view)
        else:
            send_did_save, include_text = self.should_notify_did_save()
            if send_did_save:
                self.purge_changes_async(view)
                self.session.send_notification(did_save(view, include_text, self.last_known_uri))
        if self.should_show_diagnostics_panel:
            mgr = self.session.manager()
            if mgr:
                mgr.show_diagnostics_panel_async()

    def some_view(self) -> Optional[sublime.View]:
        for sv in self.session_views:
            return sv.view
        return None

    def _if_view_unchanged(self, f: Callable[[sublime.View, Any], None], version: int) -> Callable[[Any], None]:
        """
        Ensures that the view is at the same version when we were called, before calling the `f` function.
        """
        def handler(*args: Any) -> None:
            view = self.some_view()
            if view and view.change_count() == version:
                f(view, *args)

        return handler

    # --- textDocument/documentColor -----------------------------------------------------------------------------------

    def _do_color_boxes_async(self, view: sublime.View, version: int) -> None:
        if self.session.has_capability("colorProvider"):
            self.session.send_request_async(
                Request.documentColor(document_color_params(view), view),
                self._if_view_unchanged(self._on_color_boxes_async, version)
            )

    def _on_color_boxes_async(self, view: sublime.View, response: Any) -> None:
        color_infos = response if response else []
        self.color_phantoms.update([lsp_color_to_phantom(view, color_info) for color_info in color_infos])

    # --- textDocument/documentLink ------------------------------------------------------------------------------------

    def _do_document_link_async(self, view: sublime.View, version: int) -> None:
        if self.session.has_capability("documentLinkProvider"):
            self.session.send_request_async(
                Request.documentLink({'textDocument': text_document_identifier(view)}, view),
                self._if_view_unchanged(self._on_document_link_async, version)
            )

    def _on_document_link_async(self, view: sublime.View, response: Optional[List[DocumentLink]]) -> None:
        self.document_links = response or []
        if self.document_links and userprefs().link_highlight_style == "underline":
            view.add_regions(
                "lsp_document_link",
                [range_to_region(Range.from_lsp(link["range"]), view) for link in self.document_links],
                scope="markup.underline.link.lsp",
                flags=DOCUMENT_LINK_FLAGS)
        else:
            view.erase_regions("lsp_document_link")

    def get_document_link_at_point(self, view: sublime.View, point: int) -> Optional[DocumentLink]:
        for link in self.document_links:
            if range_to_region(Range.from_lsp(link["range"]), view).contains(point):
                return link
        else:
            return None

    def update_document_link(self, new_link: DocumentLink) -> None:
        new_link_range = Range.from_lsp(new_link["range"])
        for link in self.document_links:
            if Range.from_lsp(link["range"]) == new_link_range:
                self.document_links.remove(link)
                self.document_links.append(new_link)
                break

    # --- textDocument/publishDiagnostics ------------------------------------------------------------------------------

    def on_diagnostics_async(self, raw_diagnostics: List[Diagnostic], version: Optional[int]) -> None:
        data_per_severity = {}  # type: Dict[Tuple[int, bool], DiagnosticSeverityData]
        total_errors = 0
        total_warnings = 0
        should_show_diagnostics_panel = False
        view = self.some_view()
        if view is None:
            return
        change_count = view.change_count()
        if version is None:
            version = change_count
        if version == change_count:
            diagnostics_version = version
            diagnostics = []  # type: List[Tuple[Diagnostic, sublime.Region]]
            for diagnostic in raw_diagnostics:
                region = range_to_region(Range.from_lsp(diagnostic["range"]), view)
                severity = diagnostic_severity(diagnostic)
                key = (severity, len(view.split_by_newlines(region)) > 1)
                data = data_per_severity.get(key)
                if data is None:
                    data = DiagnosticSeverityData(severity)
                    data_per_severity[key] = data
                tags = diagnostic.get('tags', [])
                if tags:
                    for tag in tags:
                        data.regions_with_tag.setdefault(tag, []).append(region)
                else:
                    data.regions.append(region)
                diagnostics.append((diagnostic, region))
                if severity == DiagnosticSeverity.Error:
                    total_errors += 1
                elif severity == DiagnosticSeverity.Warning:
                    total_warnings += 1
                if severity <= userprefs().show_diagnostics_panel_on_save:
                    should_show_diagnostics_panel = True
            self._publish_diagnostics_to_session_views(
                diagnostics_version,
                diagnostics,
                data_per_severity,
                total_errors,
                total_warnings,
                should_show_diagnostics_panel
            )

    def _publish_diagnostics_to_session_views(
        self,
        diagnostics_version: int,
        diagnostics: List[Tuple[Diagnostic, sublime.Region]],
        data_per_severity: Dict[Tuple[int, bool], DiagnosticSeverityData],
        total_errors: int,
        total_warnings: int,
        should_show_diagnostics_panel: bool
    ) -> None:

        def present() -> None:
            self._present_diagnostics_async(
                diagnostics_version,
                diagnostics,
                data_per_severity,
                total_errors,
                total_warnings,
                should_show_diagnostics_panel
            )

        self.diagnostics_debouncer.cancel_pending()

        if self.diagnostics_are_visible:
            # Old diagnostics are visible. Update immediately.
            present()
        else:
            # There were no diagnostics visible before. Show them a bit later.
            delay_in_seconds = userprefs().diagnostics_delay_ms / 1000.0 + self.last_text_change_time - time.time()
            view = self.some_view()
            if view is None:
                return
            if view.is_auto_complete_visible():
                delay_in_seconds += userprefs().diagnostics_additional_delay_auto_complete_ms / 1000.0
            if delay_in_seconds <= 0.0:
                present()
            else:
                self.diagnostics_debouncer.debounce(
                    present,
                    timeout_ms=int(1000.0 * delay_in_seconds),
                    condition=lambda: bool(view and view.is_valid() and view.change_count() == diagnostics_version),
                    async_thread=True
                )

    def _present_diagnostics_async(
        self,
        diagnostics_version: int,
        diagnostics: List[Tuple[Diagnostic, sublime.Region]],
        data_per_severity: Dict[Tuple[int, bool], DiagnosticSeverityData],
        total_errors: int,
        total_warnings: int,
        should_show_diagnostics_panel: bool
    ) -> None:
        self.diagnostics_version = diagnostics_version
        self.diagnostics = diagnostics
        self.data_per_severity = data_per_severity
        self.diagnostics_are_visible = bool(diagnostics)
        self.total_errors = total_errors
        self.total_warnings = total_warnings
        self.should_show_diagnostics_panel = should_show_diagnostics_panel
        for sv in self.session_views:
            sv.present_diagnostics_async()

    # --- textDocument/semanticTokens ----------------------------------------------------------------------------------

    def do_semantic_tokens_async(self, view: sublime.View) -> None:
        if not userprefs().semantic_highlighting:
            return
        if not self.session.has_capability("semanticTokensProvider"):
            return
        # semantic highlighting requires a special rule in the color scheme for the View.add_regions workaround
        if "background" not in view.style_for_scope("meta.semantic-token"):
            return
        if self.semantic_tokens.pending_response:
            self.session.cancel_request(self.semantic_tokens.pending_response)
        self.semantic_tokens.view_change_count = view.change_count()
        params = {"textDocument": text_document_identifier(view)}  # type: Dict[str, Any]
        if self.semantic_tokens.result_id and self.session.has_capability("semanticTokensProvider.full.delta"):
            params["previousResultId"] = self.semantic_tokens.result_id
            request = Request.semanticTokensFullDelta(params, view)
            self.semantic_tokens.pending_response = self.session.send_request_async(
                request, self._on_semantic_tokens_delta_async, self._on_semantic_tokens_error_async)
        elif self.session.has_capability("semanticTokensProvider.full"):
            request = Request.semanticTokensFull(params, view)
            self.semantic_tokens.pending_response = self.session.send_request_async(
                request, self._on_semantic_tokens_async, self._on_semantic_tokens_error_async)
        elif self.session.has_capability("semanticTokensProvider.range"):
            params["range"] = region_to_range(view, view.visible_region()).to_lsp()
            request = Request.semanticTokensRange(params, view)
            self.semantic_tokens.pending_response = self.session.send_request_async(
                request, self._on_semantic_tokens_async, self._on_semantic_tokens_error_async)

    def _on_semantic_tokens_async(self, response: Optional[Dict]) -> None:
        if response:
            self.semantic_tokens.pending_response = None
            self.semantic_tokens.result_id = response.get("resultId")
            self.semantic_tokens.data = response["data"]
            self._draw_semantic_tokens_async()

    def _on_semantic_tokens_delta_async(self, response: Optional[Dict]) -> None:
        if response:
            self.semantic_tokens.pending_response = None
            self.semantic_tokens.result_id = response.get("resultId")
            if "edits" in response:  # response is of type SemanticTokensDelta
                for semantic_tokens_edit in response["edits"]:
                    start = semantic_tokens_edit["start"]
                    end = start + semantic_tokens_edit["deleteCount"]
                    del self.semantic_tokens.data[start:end]
                    data = semantic_tokens_edit.get("data")
                    if data:
                        self.semantic_tokens.data[start:start] = data
            elif "data" in response:  # response is of type SemanticTokens
                self.semantic_tokens.data = response["data"]
            else:
                return
            self._draw_semantic_tokens_async()

    def _on_semantic_tokens_error_async(self, error: dict) -> None:
        self.semantic_tokens.pending_response = None
        self.semantic_tokens.result_id = None

    def _draw_semantic_tokens_async(self) -> None:
        view = self.some_view()
        if view is None:
            return
        self.semantic_tokens.tokens.clear()
        scope_regions = dict()  # type: Dict[int, Tuple[str, List[sublime.Region]]]
        prev_line = 0
        prev_col_utf16 = 0
        for idx in range(0, len(self.semantic_tokens.data), 5):
            delta_line = self.semantic_tokens.data[idx]
            delta_start_utf16 = self.semantic_tokens.data[idx + 1]
            length_utf16 = self.semantic_tokens.data[idx + 2]
            token_type_encoded = self.semantic_tokens.data[idx + 3]
            token_modifiers_encoded = self.semantic_tokens.data[idx + 4]
            line = prev_line + delta_line
            col_utf16 = prev_col_utf16 + delta_start_utf16 if delta_line == 0 else delta_start_utf16
            a = view.text_point_utf16(line, col_utf16, clamp_column=False)
            b = view.text_point_utf16(line, col_utf16 + length_utf16, clamp_column=False)
            r = sublime.Region(a, b)
            prev_line = line
            prev_col_utf16 = col_utf16
            token_type, token_modifiers, scope = self.session.decode_semantic_token(
                token_type_encoded, token_modifiers_encoded)
            if scope is None:
                # We can still use the meta scope and draw highlighting regions for custom token types if there is a
                # color scheme rule for this particular token type.
                # This logic should not be cached (in the decode_semantic_token method) because otherwise new user
                # customizations in the color scheme for the scopes of custom token types would require a restart of
                # Sublime Text to take effect.
                token_general_style = view.style_for_scope("meta.semantic-token")
                token_type_style = view.style_for_scope("meta.semantic-token.{}".format(token_type.lower()))
                if token_general_style["source_line"] != token_type_style["source_line"] or \
                        token_general_style["source_column"] != token_type_style["source_column"]:
                    if token_modifiers:
                        scope = "meta.semantic-token.{}.{}.lsp".format(token_type.lower(), token_modifiers[0].lower())
                    else:
                        scope = "meta.semantic-token.{}.lsp".format(token_type.lower())
            self.semantic_tokens.tokens.append(SemanticToken(r, token_type, token_modifiers))
            if scope:
                scope_regions.setdefault(self._get_semantic_region_key_for_scope(scope), (scope, []))[1].append(r)
        # don't update regions if there were additional changes to the buffer in the meantime
        if self.semantic_tokens.view_change_count != view.change_count():
            return
        for region_key in self.semantic_tokens.active_region_keys.copy():
            if region_key not in scope_regions.keys():
                self.semantic_tokens.active_region_keys.remove(region_key)
                for sv in self.session_views:
                    sv.view.erase_regions("lsp_semantic_{}".format(region_key))
        for region_key, (scope, regions) in scope_regions.items():
            if region_key not in self.semantic_tokens.active_region_keys:
                self.semantic_tokens.active_region_keys.add(region_key)
            for sv in self.session_views:
                sv.view.add_regions("lsp_semantic_{}".format(region_key), regions, scope, flags=sublime.DRAW_NO_OUTLINE)

    def _get_semantic_region_key_for_scope(self, scope: str) -> int:
        if scope not in self._semantic_region_keys:
            self._last_semantic_region_key += 1
            self._semantic_region_keys[scope] = self._last_semantic_region_key
        return self._semantic_region_keys[scope]

    def _clear_semantic_token_regions(self, view: sublime.View) -> None:
        for region_key in self.semantic_tokens.active_region_keys:
            view.erase_regions("lsp_semantic_{}".format(region_key))

    def set_semantic_tokens_pending_refresh(self, needs_refresh: bool = True) -> None:
        self.semantic_tokens.needs_refresh = needs_refresh

    def get_semantic_tokens(self) -> List[SemanticToken]:
        return self.semantic_tokens.tokens

    # --- textDocument/inlayHint ----------------------------------------------------------------------------------

    def do_inlay_hints_async(self, view: sublime.View) -> None:
        if not userprefs().show_inlay_hints:
            return
        if not self.session.has_capability("inlayHintProvider"):
            return
        params = {
            "textDocument": text_document_identifier(view),
            "range": entire_content_range(view).to_lsp()
        }  # type: InlayHintParams
        self.session.send_request_async(Request.inlayHint(params, view), self._on_inlay_hints_async)

    def _on_inlay_hints_async(self, response: InlayHintResponse) -> None:
        if response:
            view = self.some_view()
            if not view:
                return
            phantoms = [inlay_hint_to_phantom(view, inlay_hint, self.session) for inlay_hint in response]
            sublime.set_timeout(lambda: self.present_inlay_hints(phantoms))
        else:
            sublime.set_timeout(lambda: self.remove_all_inlay_hints())

    def present_inlay_hints(self, phantoms: List[sublime.Phantom]) -> None:
        self._inlay_hints_phantom_set.update(phantoms)

    def remove_inlay_hint_phantom(self, phantom_uuid: str) -> None:
        new_phantoms = list(filter(
            lambda p: getattr(p, 'lsp_uuid') != phantom_uuid,
            self._inlay_hints_phantom_set.phantoms)
        )
        self._inlay_hints_phantom_set.update(new_phantoms)

    def remove_all_inlay_hints(self) -> None:
        self._inlay_hints_phantom_set.update([])

    # ------------------------------------------------------------------------------------------------------------------

    def __str__(self) -> str:
        return '{}:{}:{}'.format(self.session.config.name, self.id, self.get_uri())
