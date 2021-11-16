from .core.protocol import Diagnostic
from .core.protocol import DiagnosticSeverity
from .core.protocol import DocumentUri
from .core.protocol import Range
from .core.protocol import Request
from .core.protocol import TextDocumentSyncKindFull
from .core.protocol import TextDocumentSyncKindNone
from .core.sessions import SessionViewProtocol
from .core.settings import userprefs
from .core.types import Capabilities
from .core.types import debounced
from .core.types import Debouncer
from .core.types import FEATURES_TIMEOUT
from .core.typing import Any, Callable, Iterable, Optional, List, Dict, Tuple
from .core.views import DIAGNOSTIC_SEVERITY
from .core.views import diagnostic_severity
from .core.views import did_change
from .core.views import did_close
from .core.views import did_open
from .core.views import did_save
from .core.views import document_color_params
from .core.views import lsp_color_to_phantom
from .core.views import MissingUriError
from .core.views import range_to_region
from .core.views import will_save
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
        self.session = session_view.session
        self.session_views = WeakSet()  # type: WeakSet[SessionViewProtocol]
        self.session_views.add(session_view)
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
        self._check_did_open(view)
        self.session.register_session_buffer_async(self)

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

    def _check_did_open(self, view: sublime.View) -> None:
        if not self.opened and self.should_notify_did_open():
            language_id = self.get_language_id()
            if not language_id:
                # we're closing
                return
            self.session.send_notification(did_open(view, language_id))
            self.opened = True
            self._do_color_boxes_async(view, view.change_count())
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

    def __str__(self) -> str:
        return '{}:{}:{}'.format(self.session.config.name, self.id, self.get_uri())
