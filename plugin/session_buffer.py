from __future__ import annotations
from ..protocol import CodeLens
from ..protocol import ColorInformation
from ..protocol import Diagnostic
from ..protocol import DocumentDiagnosticParams
from ..protocol import DocumentDiagnosticReport
from ..protocol import DocumentDiagnosticReportKind
from ..protocol import DocumentLink
from ..protocol import DocumentUri
from ..protocol import FullDocumentDiagnosticReport
from ..protocol import InlayHint
from ..protocol import InlayHintParams
from ..protocol import LSPErrorCodes
from ..protocol import SemanticTokensDeltaParams
from ..protocol import SemanticTokensParams
from ..protocol import SemanticTokensRangeParams
from ..protocol import TextDocumentSaveReason
from ..protocol import TextDocumentSyncKind
from .code_lens import LspToggleCodeLensesCommand
from .core.constants import DOCUMENT_LINK_FLAGS
from .core.constants import RegionKey
from .core.constants import SEMANTIC_TOKEN_FLAGS
from .core.protocol import Request
from .core.protocol import ResponseError
from .core.sessions import is_diagnostic_server_cancellation_data
from .core.sessions import Session
from .core.sessions import SessionViewProtocol
from .core.settings import userprefs
from .core.types import Capabilities
from .core.types import debounced
from .core.types import DebouncerNonThreadSafe
from .core.types import FEATURES_TIMEOUT
from .core.types import WORKSPACE_DIAGNOSTICS_TIMEOUT
from .core.views import diagnostic_severity
from .core.views import DiagnosticSeverityData
from .core.views import did_change
from .core.views import did_close
from .core.views import did_open
from .core.views import did_save
from .core.views import document_color_params
from .core.views import entire_content_range
from .core.views import lsp_color_to_phantom
from .core.views import MissingUriError
from .core.views import range_to_region
from .core.views import region_to_range
from .core.views import text_document_identifier
from .core.views import will_save
from .inlay_hint import inlay_hint_to_phantom
from .semantic_highlighting import SemanticToken
from functools import partial
from typing import Any, Callable, Iterable, List, Protocol
from typing import cast
from typing_extensions import TypeGuard
from typing_extensions import deprecated
from weakref import WeakSet
import sublime
import time


# If the total number of characters in the file exceeds this limit, try to send a semantic tokens request only for the
# visible part first when the file was just opened
HUGE_FILE_SIZE = 50000


class CallableWithOptionalArguments(Protocol):
    def __call__(self, *args: Any) -> None:
        ...


def is_full_document_diagnostic_report(response: DocumentDiagnosticReport) -> TypeGuard[FullDocumentDiagnosticReport]:
    return response['kind'] == DocumentDiagnosticReportKind.Full


class PendingChanges:

    __slots__ = ('version', 'changes')

    def __init__(self, version: int, changes: Iterable[sublime.TextChange]) -> None:
        self.version = version
        self.changes = list(changes)

    def update(self, version: int, changes: Iterable[sublime.TextChange]) -> None:
        self.version = version
        self.changes.extend(changes)


class PendingDocumentDiagnosticRequest:

    __slots__ = ('version', 'request_id')

    def __init__(self, version: int, request_id: int) -> None:
        self.version = version
        self.request_id = request_id


class SemanticTokensData:

    __slots__ = (
        'data', 'result_id', 'active_region_keys', 'tokens', 'view_change_count', 'needs_refresh', 'pending_response')

    def __init__(self) -> None:
        self.data: list[int] = []
        self.result_id: str | None = None
        self.active_region_keys: set[int] = set()
        self.tokens: list[SemanticToken] = []
        self.view_change_count = 0
        self.needs_refresh = False
        self.pending_response: int | None = None


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
        self._session_views: WeakSet[SessionViewProtocol] = WeakSet()
        self._session_views.add(session_view)
        self._last_known_uri = uri
        self._id = buffer_id
        self._pending_changes: PendingChanges | None = None
        self.diagnostics: list[tuple[Diagnostic, sublime.Region]] = []
        self.diagnostics_data_per_severity: dict[tuple[int, bool], DiagnosticSeverityData] = {}
        self._diagnostics_version = -1
        self.diagnostics_flags = 0
        self._diagnostics_are_visible = False
        self.document_diagnostic_needs_refresh = False
        self._document_diagnostic_pending_request: PendingDocumentDiagnosticRequest | None = None
        self._last_synced_version = 0
        self._last_text_change_time = 0.0
        self._diagnostics_debouncer_async = DebouncerNonThreadSafe(async_thread=True)
        self._workspace_diagnostics_debouncer_async = DebouncerNonThreadSafe(async_thread=True)
        self._color_phantoms = sublime.PhantomSet(view, "lsp_color")
        self._document_links: list[DocumentLink] = []
        self.semantic_tokens = SemanticTokensData()
        self._semantic_region_keys: dict[str, int] = {}
        self._last_semantic_region_key = 0
        self._inlay_hints_phantom_set = sublime.PhantomSet(view, "lsp_inlay_hints")
        self.inlay_hints_needs_refresh = False
        self.code_lenses_needs_refresh = False
        self._is_saving = False
        self._has_changed_during_save = False
        self._dynamically_registered_commands: dict[str, list[str]] = {}
        self._supported_commands: set[str] = set()
        self._update_supported_commands()
        self._check_did_open(view)

    @property
    def session(self) -> Session:
        return self._session

    @property
    def session_views(self) -> WeakSet[SessionViewProtocol]:
        return self._session_views

    @property
    def last_synced_version(self) -> int:
        return self._last_synced_version

    @property
    def supported_commands(self) -> set[str]:
        return self._supported_commands

    def _check_did_open(self, view: sublime.View) -> None:
        if not self.opened and self.should_notify_did_open():
            language_id = self.get_language_id()
            if not language_id:
                # we're closing
                return
            self.session.send_notification(did_open(view, language_id))
            self.opened = True
            version = view.change_count()
            self._last_synced_version = version
            self._do_color_boxes_async(view, version)
            self.do_document_diagnostic_async(view, version)
            self.do_semantic_tokens_async(view, view.size() > HUGE_FILE_SIZE)
            self.do_inlay_hints_async(view)
            self.do_code_lenses_async(view)
            if userprefs().link_highlight_style in ("underline", "none"):
                self._do_document_link_async(view, version)
            self.session.notify_plugin_on_session_buffer_change(self)

    def _check_did_close(self, view: sublime.View) -> None:
        if self.opened and self.should_notify_did_close():
            self.purge_changes_async(view, suppress_requests=True)
            self.session.send_notification(did_close(uri=self._last_known_uri))
            self.opened = False

    def get_uri(self) -> DocumentUri | None:
        for sv in self.session_views:
            return sv.get_uri()
        return None

    def get_language_id(self) -> str | None:
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
    @deprecated("Use get_language_id() instead")
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
        if len(self.session_views) == 0:
            self._on_before_destroy(sv.view)

    def _on_before_destroy(self, view: sublime.View) -> None:
        self.remove_all_inlay_hints()
        if self.has_capability("diagnosticProvider") and self.session.config.diagnostics_mode == "open_files":
            self.session.m_textDocument_publishDiagnostics({'uri': self._last_known_uri, 'diagnostics': []})
        wm = self.session.manager()
        if wm:
            wm.on_diagnostics_updated()
        self._color_phantoms.update([])
        # If the session is exiting then there's no point in sending textDocument/didClose and there's also no point
        # in unregistering ourselves from the session.
        if not self.session.exiting:
            # Only send textDocument/didClose when we are the only view left (i.e. there are no other clones).
            self._check_did_close(view)
            self.session.unregister_session_buffer_async(self)

    def register_capability_async(
        self,
        registration_id: str,
        capability_path: str,
        registration_path: str,
        options: dict[str, Any]
    ) -> None:
        self.capabilities.register(registration_id, capability_path, registration_path, options)
        view: sublime.View | None = None
        for sv in self.session_views:
            sv.on_capability_added_async(registration_id, capability_path, options)
            if view is None:
                view = sv.view
        if view is not None:
            if capability_path.startswith("textDocumentSync."):
                self._check_did_open(view)
            elif capability_path.startswith("diagnosticProvider"):
                self.do_document_diagnostic_async(view, view.change_count())
            elif capability_path.startswith("codeLensProvider"):
                self.do_code_lenses_async(view)
            elif capability_path == "executeCommandProvider":
                self._dynamically_registered_commands[registration_id] = options['commands']
                self._update_supported_commands()

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
        if capability_path == "executeCommandProvider":
            self._dynamically_registered_commands.pop(registration_id)
            self._update_supported_commands()

    def get_capability(self, capability_path: str) -> Any | None:
        if self.session.config.is_disabled_capability(capability_path):
            return None
        value = self.capabilities.get(capability_path)
        return value if value is not None else self.session.capabilities.get(capability_path)

    def has_capability(self, capability_path: str) -> bool:
        value = self.get_capability(capability_path)
        return value is not False and value is not None

    def text_sync_kind(self) -> TextDocumentSyncKind:
        value = self.capabilities.text_sync_kind()
        return value if value != TextDocumentSyncKind.None_ else self.session.text_sync_kind()

    def should_notify_did_open(self) -> bool:
        return self.capabilities.should_notify_did_open() or self.session.should_notify_did_open()

    def should_notify_will_save(self) -> bool:
        return self.capabilities.should_notify_will_save() or self.session.should_notify_will_save()

    def should_notify_did_save(self) -> tuple[bool, bool]:
        do_it, include_text = self.capabilities.should_notify_did_save()
        return (do_it, include_text) if do_it else self.session.should_notify_did_save()

    def should_notify_did_close(self) -> bool:
        return self.capabilities.should_notify_did_close() or self.session.should_notify_did_close()

    def on_text_changed_async(self, view: sublime.View, change_count: int,
                              changes: Iterable[sublime.TextChange]) -> None:
        if change_count <= self._last_synced_version:
            return
        self._last_text_change_time = time.time()
        last_change = list(changes)[-1]
        if last_change.a.pt == 0 and last_change.b.pt == 0 and last_change.str == '' and view.size() != 0:
            # Issue https://github.com/sublimehq/sublime_text/issues/3323
            # A special situation when changes externally. We receive two changes,
            # one that removes all content and one that has 0,0,'' parameters.
            pass
        else:
            purge = False
            if self._pending_changes is None:
                self._pending_changes = PendingChanges(change_count, changes)
                purge = True
            elif self._pending_changes.version < change_count:
                self._pending_changes.update(change_count, changes)
                purge = True
            if purge:
                self._cancel_pending_requests_async()
                debounced(lambda: self.purge_changes_async(view), FEATURES_TIMEOUT,
                          lambda: view.is_valid() and change_count == view.change_count(), async_thread=True)

    def _cancel_pending_requests_async(self) -> None:
        if self._document_diagnostic_pending_request:
            self.session.cancel_request(self._document_diagnostic_pending_request.request_id)
            self._document_diagnostic_pending_request = None
        if self.semantic_tokens.pending_response:
            self.session.cancel_request(self.semantic_tokens.pending_response)
            self.semantic_tokens.pending_response = None

    def on_revert_async(self, view: sublime.View) -> None:
        self._pending_changes = None  # Don't bother with pending changes
        version = view.change_count()
        self.session.send_notification(did_change(view, version, None))
        sublime.set_timeout_async(lambda: self._on_after_change_async(view, version))

    on_reload_async = on_revert_async

    def purge_changes_async(self, view: sublime.View, suppress_requests: bool = False) -> None:
        if self._pending_changes is None:
            return
        sync_kind = self.text_sync_kind()
        if sync_kind == TextDocumentSyncKind.None_:
            return
        if sync_kind == TextDocumentSyncKind.Full:
            changes = None
            version = view.change_count() or self._pending_changes.version
        else:
            changes = self._pending_changes.changes
            version = self._pending_changes.version
        try:
            notification = did_change(view, version, changes)
            self.session.send_notification(notification)
            self._last_synced_version = version
        except MissingUriError:
            return  # we're closing
        finally:
            self._pending_changes = None
        self.session.notify_plugin_on_session_buffer_change(self)
        sublime.set_timeout_async(lambda: self._on_after_change_async(view, version, suppress_requests))

    def _on_after_change_async(self, view: sublime.View, version: int, suppress_requests: bool = False) -> None:
        if self._is_saving:
            self._has_changed_during_save = True
            return
        if suppress_requests:
            return
        try:
            self._do_color_boxes_async(view, version)
            self.do_document_diagnostic_async(view, version)
            if self.session.config.diagnostics_mode == "workspace" and \
                    not self.session.workspace_diagnostics_pending_response and \
                    self.session.has_capability('diagnosticProvider.workspaceDiagnostics'):
                self._workspace_diagnostics_debouncer_async.debounce(
                    self.session.do_workspace_diagnostics_async, timeout_ms=WORKSPACE_DIAGNOSTICS_TIMEOUT)
            self.do_semantic_tokens_async(view)
            if userprefs().link_highlight_style in ("underline", "none"):
                self._do_document_link_async(view, version)
            self.do_inlay_hints_async(view)
            self.do_code_lenses_async(view)
        except MissingUriError:
            pass

    def on_pre_save_async(self, view: sublime.View) -> None:
        self._is_saving = True
        if self.should_notify_will_save():
            self.purge_changes_async(view)
            # TextDocumentSaveReason.Manual
            self.session.send_notification(will_save(self._last_known_uri, TextDocumentSaveReason.Manual))

    def on_post_save_async(self, view: sublime.View, new_uri: DocumentUri) -> None:
        self._is_saving = False
        if new_uri != self._last_known_uri:
            self._check_did_close(view)
            self._last_known_uri = new_uri
            self._check_did_open(view)
        else:
            send_did_save, include_text = self.should_notify_did_save()
            if send_did_save:
                self.purge_changes_async(view)
                self.session.send_notification(did_save(view, include_text, self._last_known_uri))
        if self._has_changed_during_save:
            self._has_changed_during_save = False
            self._on_after_change_async(view, view.change_count())

    def on_userprefs_changed_async(self) -> None:
        self._redraw_document_links_async()
        if userprefs().semantic_highlighting:
            self.semantic_tokens.needs_refresh = True
        else:
            self._clear_semantic_tokens_async()
        for sv in self.session_views:
            sv.on_userprefs_changed_async()

    def some_view(self) -> sublime.View | None:
        if not self.session_views:
            return None
        # Prefer active view if possible
        active_view = self.session.window.active_view()
        for sv in self.session_views:
            if sv.view == active_view:
                return active_view
        for sv in self.session_views:
            return sv.view

    def _if_view_unchanged(self, f: Callable[[sublime.View, Any], None], version: int) -> CallableWithOptionalArguments:
        """
        Ensures that the view is at the same version when we were called, before calling the `f` function.
        """
        def handler(*args: Any) -> None:
            view = self.some_view()
            if view and view.change_count() == version:
                f(view, *args)

        return handler

    def _update_supported_commands(self) -> None:
        self._supported_commands = set(self.session.get_capability('executeCommandProvider.commands') or [])
        for commands in self._dynamically_registered_commands.values():
            for command in commands:
                self._supported_commands.add(command)

    # --- textDocument/documentColor -----------------------------------------------------------------------------------

    def _do_color_boxes_async(self, view: sublime.View, version: int) -> None:
        if self.has_capability("colorProvider"):
            self.session.send_request_async(
                Request.documentColor(document_color_params(view), view),
                self._if_view_unchanged(self._on_color_boxes_async, version)
            )

    def _on_color_boxes_async(self, view: sublime.View, response: list[ColorInformation]) -> None:
        if response is None:  # Guard against spec violation from certain language servers
            self._color_phantoms.update([])
            return
        phantoms = [lsp_color_to_phantom(view, color_info) for color_info in response]
        sublime.set_timeout(lambda: self._color_phantoms.update(phantoms))

    # --- textDocument/documentLink ------------------------------------------------------------------------------------

    def _do_document_link_async(self, view: sublime.View, version: int) -> None:
        if self.has_capability("documentLinkProvider"):
            self.session.send_request_async(
                Request.documentLink({'textDocument': text_document_identifier(view)}, view),
                self._if_view_unchanged(self._on_document_link_async, version)
            )

    def _on_document_link_async(self, view: sublime.View, response: list[DocumentLink] | None) -> None:
        self._document_links = response or []
        self._redraw_document_links_async()

    def _redraw_document_links_async(self) -> None:
        if self._document_links and userprefs().link_highlight_style == "underline":
            view = self.some_view()
            if not view:
                return
            regions = [range_to_region(link["range"], view) for link in self._document_links]
            for sv in self.session_views:
                sv.view.add_regions(
                    RegionKey.DOCUMENT_LINK, regions, scope="markup.underline.link.lsp", flags=DOCUMENT_LINK_FLAGS)
        else:
            for sv in self.session_views:
                sv.view.erase_regions(RegionKey.DOCUMENT_LINK)

    def get_document_link_at_point(self, view: sublime.View, point: int) -> DocumentLink | None:
        for link in self._document_links:
            if range_to_region(link["range"], view).contains(point):
                return link
        else:
            return None

    def update_document_link(self, new_link: DocumentLink) -> None:
        new_link_range = new_link["range"]
        for link in self._document_links:
            if link["range"] == new_link_range:
                self._document_links.remove(link)
                self._document_links.append(new_link)
                break

    # --- textDocument/diagnostic --------------------------------------------------------------------------------------

    def do_document_diagnostic_async(self, view: sublime.View, version: int, *, forced_update: bool = False) -> None:
        mgr = self.session.manager()
        if not mgr or not self.has_capability("diagnosticProvider"):
            return
        if mgr.should_ignore_diagnostics(self._last_known_uri, self.session.config):
            return
        if version < view.change_count() or version == self._diagnostics_version:
            return
        if self._document_diagnostic_pending_request:
            if self._document_diagnostic_pending_request.version == version and not forced_update:
                return
            self.session.cancel_request(self._document_diagnostic_pending_request.request_id)
        params: DocumentDiagnosticParams = {'textDocument': text_document_identifier(view)}
        identifier = self.get_capability("diagnosticProvider.identifier")
        if identifier:
            params['identifier'] = identifier
        result_id = self.session.diagnostics_result_ids.get(self._last_known_uri)
        if result_id is not None:
            params['previousResultId'] = result_id
        request_id = self.session.send_request_async(
            Request.documentDiagnostic(params, view),
            partial(self._on_document_diagnostic_async, version),
            partial(self._on_document_diagnostic_error_async, version)
        )
        self._document_diagnostic_pending_request = PendingDocumentDiagnosticRequest(version, request_id)

    def _on_document_diagnostic_async(self, version: int, response: DocumentDiagnosticReport) -> None:
        self._document_diagnostic_pending_request = None
        self._if_view_unchanged(self._apply_document_diagnostic_async, version)(response)

    def _apply_document_diagnostic_async(self, view: sublime.View | None, response: DocumentDiagnosticReport) -> None:
        self.session.diagnostics_result_ids[self._last_known_uri] = response.get('resultId')
        if is_full_document_diagnostic_report(response):
            self.session.m_textDocument_publishDiagnostics(
                {'uri': self._last_known_uri, 'diagnostics': response['items']})
        if 'relatedDocuments' in response:
            for uri, diagnostic_report in response['relatedDocuments'].items():
                sb = self.session.get_session_buffer_for_uri_async(uri)
                if sb:
                    cast(SessionBuffer, sb)._apply_document_diagnostic_async(
                        None, cast(DocumentDiagnosticReport, diagnostic_report))

    def _on_document_diagnostic_error_async(self, version: int, error: ResponseError) -> None:
        self._document_diagnostic_pending_request = None
        if error['code'] == LSPErrorCodes.ServerCancelled:
            data = error.get('data')
            if is_diagnostic_server_cancellation_data(data) and data['retriggerRequest']:
                # Retrigger the request after a short delay, but only if there were no additional changes to the buffer
                # (in that case the request will be retriggered automatically anyway)
                sublime.set_timeout_async(
                    lambda: self._if_view_unchanged(self.do_document_diagnostic_async, version)(version), 500)

    def set_document_diagnostic_pending_refresh(self, needs_refresh: bool = True) -> None:
        self.document_diagnostic_needs_refresh = needs_refresh

    # --- textDocument/publishDiagnostics ------------------------------------------------------------------------------

    def on_diagnostics_async(
        self, raw_diagnostics: list[Diagnostic], version: int, visible_session_views: set[SessionViewProtocol]
    ) -> None:
        view = self.some_view()
        if view is None:
            return
        if version != view.change_count():
            return
        diagnostics_version = version
        diagnostics: list[tuple[Diagnostic, sublime.Region]] = []
        data_per_severity: dict[tuple[int, bool], DiagnosticSeverityData] = {}
        for diagnostic in raw_diagnostics:
            region = range_to_region(diagnostic["range"], view)
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
        self.diagnostics_data_per_severity = data_per_severity

        def present() -> None:
            self._diagnostics_version = diagnostics_version
            self.diagnostics = diagnostics
            self._diagnostics_are_visible = bool(diagnostics)
            for sv in self.session_views:
                sv.present_diagnostics_async(sv in visible_session_views)

        self._diagnostics_debouncer_async.cancel_pending()
        if self._diagnostics_are_visible:
            # Old diagnostics are visible. Update immediately.
            present()
        else:
            # There were no diagnostics visible before. Show them a bit later.
            delay_in_seconds = userprefs().diagnostics_delay_ms / 1000.0 + self._last_text_change_time - time.time()
            if view.is_auto_complete_visible():
                delay_in_seconds += userprefs().diagnostics_additional_delay_auto_complete_ms / 1000.0
            if delay_in_seconds <= 0.0:
                present()
            else:
                self._diagnostics_debouncer_async.debounce(
                    present,
                    timeout_ms=int(1000.0 * delay_in_seconds),
                    condition=lambda: bool(view and view.is_valid() and view.change_count() == diagnostics_version),
                )

    def has_latest_diagnostics(self) -> bool:
        view = self.some_view()
        if view is None:
            return False
        return self._diagnostics_version == view.change_count()

    # --- textDocument/semanticTokens ----------------------------------------------------------------------------------

    def do_semantic_tokens_async(self, view: sublime.View, only_viewport: bool = False) -> None:
        if not userprefs().semantic_highlighting:
            return
        if not self.has_capability("semanticTokensProvider"):
            return
        # semantic highlighting requires a special rule in the color scheme for the View.add_regions workaround
        if "background" not in view.style_for_scope("meta.semantic-token"):
            return
        if self.semantic_tokens.pending_response:
            self.session.cancel_request(self.semantic_tokens.pending_response)
        self.semantic_tokens.view_change_count = view.change_count()
        params: dict[str, Any] = {"textDocument": text_document_identifier(view)}
        if only_viewport and self.has_capability("semanticTokensProvider.range"):
            params["range"] = region_to_range(view, view.visible_region())
            request = Request.semanticTokensRange(cast(SemanticTokensRangeParams, params), view)
            self.semantic_tokens.pending_response = self.session.send_request_async(
                request, partial(self._on_semantic_tokens_viewport_async, view), self._on_semantic_tokens_error_async)
        elif self.semantic_tokens.result_id and self.has_capability("semanticTokensProvider.full.delta"):
            params["previousResultId"] = self.semantic_tokens.result_id
            request = Request.semanticTokensFullDelta(cast(SemanticTokensDeltaParams, params), view)
            self.semantic_tokens.pending_response = self.session.send_request_async(
                request, self._on_semantic_tokens_delta_async, self._on_semantic_tokens_error_async)
        elif self.has_capability("semanticTokensProvider.full"):
            request = Request.semanticTokensFull(cast(SemanticTokensParams, params), view)
            self.semantic_tokens.pending_response = self.session.send_request_async(
                request, self._on_semantic_tokens_async, self._on_semantic_tokens_error_async)
        elif self.has_capability("semanticTokensProvider.range"):
            params["range"] = entire_content_range(view)
            request = Request.semanticTokensRange(cast(SemanticTokensRangeParams, params), view)
            self.semantic_tokens.pending_response = self.session.send_request_async(
                request, self._on_semantic_tokens_async, self._on_semantic_tokens_error_async)

    def _on_semantic_tokens_async(self, response: dict | None) -> None:
        self.semantic_tokens.pending_response = None
        if response:
            self.semantic_tokens.result_id = response.get("resultId")
            self.semantic_tokens.data = response["data"]
            self._draw_semantic_tokens_async()

    def _on_semantic_tokens_viewport_async(self, view: sublime.View, response: dict | None) -> None:
        self._on_semantic_tokens_async(response)
        self.do_semantic_tokens_async(view)  # now request semantic tokens for the full file

    def _on_semantic_tokens_delta_async(self, response: dict | None) -> None:
        self.semantic_tokens.pending_response = None
        if response:
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

    def _on_semantic_tokens_error_async(self, _: dict) -> None:
        self.semantic_tokens.pending_response = None
        self.semantic_tokens.result_id = None

    def _draw_semantic_tokens_async(self) -> None:
        view = self.some_view()
        if view is None:
            return
        self.semantic_tokens.tokens.clear()
        scope_regions: dict[int, tuple[str, list[sublime.Region]]] = dict()
        prev_line = 0
        prev_col_utf16 = 0
        types_legend = tuple(cast(List[str], self.get_capability('semanticTokensProvider.legend.tokenTypes')))
        modifiers_legend = tuple(cast(List[str], self.get_capability('semanticTokensProvider.legend.tokenModifiers')))
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
                types_legend, modifiers_legend, token_type_encoded, token_modifiers_encoded)
            if scope is None:
                # We can still use the meta scope and draw highlighting regions for custom token types if there is a
                # color scheme rule for this particular token type.
                # This logic should not be cached (in the decode_semantic_token method) because otherwise new user
                # customizations in the color scheme for the scopes of custom token types would require a restart of
                # Sublime Text to take effect.
                token_general_style = view.style_for_scope("meta.semantic-token")
                token_type_style = view.style_for_scope(f"meta.semantic-token.{token_type.lower()}")
                if token_general_style["source_line"] != token_type_style["source_line"] or \
                        token_general_style["source_column"] != token_type_style["source_column"]:
                    if token_modifiers:
                        scope = f"meta.semantic-token.{token_type.lower()}.{token_modifiers[0].lower()}.lsp"
                    else:
                        scope = f"meta.semantic-token.{token_type.lower()}.lsp"
            self.semantic_tokens.tokens.append(SemanticToken(r, token_type, token_modifiers))
            if scope:
                scope_regions.setdefault(self._get_semantic_region_key_for_scope(scope), (scope, []))[1].append(r)
        # don't update regions if there were additional changes to the buffer in the meantime
        if self.semantic_tokens.view_change_count != view.change_count():
            return
        session_name = self.session.config.name
        for region_key in self.semantic_tokens.active_region_keys.copy():
            if region_key not in scope_regions.keys():
                self.semantic_tokens.active_region_keys.remove(region_key)
                for sv in self.session_views:
                    sv.view.erase_regions(f"lsp_semantic_{session_name}_{region_key}")
        for region_key, (scope, regions) in scope_regions.items():
            if region_key not in self.semantic_tokens.active_region_keys:
                self.semantic_tokens.active_region_keys.add(region_key)
            for sv in self.session_views:
                sv.view.add_regions(
                    f"lsp_semantic_{session_name}_{region_key}", regions, scope, flags=SEMANTIC_TOKEN_FLAGS)

    def _get_semantic_region_key_for_scope(self, scope: str) -> int:
        if scope not in self._semantic_region_keys:
            self._last_semantic_region_key += 1
            self._semantic_region_keys[scope] = self._last_semantic_region_key
        return self._semantic_region_keys[scope]

    def _clear_semantic_token_regions(self, view: sublime.View) -> None:
        session_name = self.session.config.name
        for region_key in self.semantic_tokens.active_region_keys:
            view.erase_regions(f"lsp_semantic_{session_name}_{region_key}")

    def set_semantic_tokens_pending_refresh(self, needs_refresh: bool = True) -> None:
        self.semantic_tokens.needs_refresh = needs_refresh

    def get_semantic_tokens(self) -> list[SemanticToken]:
        return self.semantic_tokens.tokens

    def _clear_semantic_tokens_async(self) -> None:
        for sv in self.session_views:
            self._clear_semantic_token_regions(sv.view)

    # --- textDocument/inlayHint ----------------------------------------------------------------------------------

    def do_inlay_hints_async(self, view: sublime.View) -> None:
        if not self.has_capability("inlayHintProvider"):
            return
        window = view.window()
        if not window:
            return
        if not window.settings().get('lsp_show_inlay_hints'):
            self.remove_all_inlay_hints()
            return
        params: InlayHintParams = {
            "textDocument": text_document_identifier(view),
            "range": entire_content_range(view)
        }
        self.session.send_request_async(Request.inlayHint(params, view), self._on_inlay_hints_async)

    def _on_inlay_hints_async(self, response: list[InlayHint] | None) -> None:
        if response:
            view = self.some_view()
            if not view:
                return
            phantoms = [inlay_hint_to_phantom(view, inlay_hint, self.session) for inlay_hint in response]
            sublime.set_timeout(lambda: self.present_inlay_hints(phantoms))
        else:
            sublime.set_timeout(lambda: self.remove_all_inlay_hints())

    def present_inlay_hints(self, phantoms: list[sublime.Phantom]) -> None:
        self._inlay_hints_phantom_set.update(phantoms)

    def set_inlay_hints_pending_refresh(self, needs_refresh: bool = True) -> None:
        self.inlay_hints_needs_refresh = needs_refresh

    def remove_inlay_hint_phantom(self, phantom_uuid: str) -> None:
        new_phantoms = list(filter(
            lambda p: getattr(p, 'lsp_uuid') != phantom_uuid,
            self._inlay_hints_phantom_set.phantoms)
        )
        self._inlay_hints_phantom_set.update(new_phantoms)

    def remove_all_inlay_hints(self) -> None:
        self._inlay_hints_phantom_set.update([])

    # --- textDocument/codeLens ----------------------------------------------------------------------------------------

    def do_code_lenses_async(self, view: sublime.View) -> None:
        if not self.has_capability('codeLensProvider'):
            return
        if not LspToggleCodeLensesCommand.are_enabled(view.window()):
            return
        for sv in self.session_views:
            if sv.view == view:
                for request_id, data in sv.active_requests.items():
                    if data.request.method == 'codeAction/resolve':
                        self.session.cancel_request(request_id)
                break
        params = {'textDocument': text_document_identifier(view)}
        self.session.send_request_async(Request('textDocument/codeLens', params, view), self._on_code_lenses_async)

    def _on_code_lenses_async(self, response: list[CodeLens] | None) -> None:
        if response is None:
            supported_code_lenses = []
        elif self.session.uses_plugin():
            supported_code_lenses = response
        else:
            # Filter out CodeLenses with unknown commands
            supported_code_lenses: list[CodeLens] = []
            for code_lens in response:
                command = code_lens.get('command')
                if command is None:
                    # The command for this CodeLens still needs to be resolved
                    supported_code_lenses.append(code_lens)
                    continue
                command_name = command['command']
                if command_name in self.supported_commands:
                    supported_code_lenses.append(code_lens)
                else:
                    self.session.check_log_unsupported_command(command_name)
        for sv in self.session_views:
            if supported_code_lenses:
                sv.handle_code_lenses_async(supported_code_lenses)
            else:
                sv.clear_code_lenses_async()

    def set_code_lenses_pending_refresh(self, needs_refresh: bool = True) -> None:
        self.code_lenses_needs_refresh = needs_refresh

    # ------------------------------------------------------------------------------------------------------------------

    def __str__(self) -> str:
        return f'{self.session.config.name}:{self._id}:{self.get_uri()}'
