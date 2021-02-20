from .core.protocol import Diagnostic
from .core.protocol import DiagnosticSeverity
from .core.protocol import DiagnosticTag
from .core.protocol import TextDocumentSyncKindFull
from .core.protocol import TextDocumentSyncKindNone
from .core.protocol import Range
from .core.sessions import SessionViewProtocol
from .core.settings import userprefs
from .core.types import Capabilities
from .core.types import debounced
from .core.types import Debouncer
from .core.types import FEATURES_TIMEOUT
from .core.typing import Any, Iterable, Optional, List, Dict, Tuple
from .core.views import DIAGNOSTIC_SEVERITY
from .core.views import diagnostic_severity
from .core.views import did_change
from .core.views import did_close
from .core.views import did_open
from .core.views import did_save
from .core.views import format_diagnostic_for_panel
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

    __slots__ = ('regions', 'annotations', 'panel_contribution', 'scope', 'icon', 'tags')

    def __init__(self, severity: int) -> None:
        self.regions = []  # type: List[sublime.Region]
        self.annotations = []  # type: List[str]
        self.panel_contribution = []  # type: List[Tuple[str, Optional[int], Optional[str], Optional[str]]]
        _, _, self.scope, self.icon = DIAGNOSTIC_SEVERITY[severity - 1]
        if userprefs().diagnostics_gutter_marker != "sign":
            self.icon = userprefs().diagnostics_gutter_marker
        self.tags = []  # type: List[int]


class SessionBuffer:
    """
    Holds state per session per buffer.

    It stores the filename, handles document synchronization for the buffer, and stores/receives diagnostics for the
    buffer. The diagnostics are then published further to the views attached to this buffer. It also maintains the
    dynamically registered capabilities applicable to this particular buffer.
    """

    def __init__(self, session_view: SessionViewProtocol, buffer_id: int, language_id: str) -> None:
        view = session_view.view
        file_name = view.file_name()
        if not file_name:
            raise ValueError("missing filename")
        self.opened = False
        # Every SessionBuffer has its own personal capabilities due to "dynamic registration".
        self.capabilities = Capabilities()
        self.session = session_view.session
        self.session_views = WeakSet()  # type: WeakSet[SessionViewProtocol]
        self.session_views.add(session_view)
        self.file_name = file_name
        self.language_id = language_id
        self.id = buffer_id
        self.pending_changes = None  # type: Optional[PendingChanges]
        self.diagnostics = []  # type: List[Tuple[Diagnostic, sublime.Region]]
        self.data_per_severity = {}  # type: Dict[int, DiagnosticSeverityData]
        self.diagnostics_version = -1
        self.diagnostics_flags = 0
        self.diagnostics_are_visible = False
        self.last_text_change_time = 0.0
        self.total_errors = 0
        self.total_warnings = 0
        self.should_show_diagnostics_panel = False
        self.diagnostics_debouncer = Debouncer()
        self._check_did_open(view)
        self.session.register_session_buffer_async(self)

    def __del__(self) -> None:
        mgr = self.session.manager()
        if mgr:
            mgr.update_diagnostics_panel_async()
        # If the session is exiting then there's no point in sending textDocument/didClose and there's also no point
        # in unregistering ourselves from the session.
        if not self.session.exiting:
            # Only send textDocument/didClose when we are the only view left (i.e. there are no other clones).
            self._check_did_close()
            self.session.unregister_session_buffer_async(self)

    def _check_did_open(self, view: sublime.View) -> None:
        if not self.opened and self.should_notify_did_open():
            self.session.send_notification(did_open(view, self.language_id))
            self.opened = True

    def _check_did_close(self) -> None:
        if self.opened and self.should_notify_did_close():
            self.session.send_notification(did_close(self.file_name))
            self.opened = False

    def add_session_view(self, sv: SessionViewProtocol) -> None:
        self.session_views.add(sv)

    def shutdown_async(self) -> None:
        for sv in self.session_views:
            listener = sv.listener()
            if listener:
                listener.on_session_shutdown_async(self.session)

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
        value = self.capabilities.get(capability_path)
        return value if value is not None else self.session.get_capability(capability_path)

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
            notification = did_change(view, version, changes)
            self.session.send_notification(notification)
            self.pending_changes = None

    def on_pre_save_async(self, view: sublime.View, old_file_name: str) -> None:
        if self.should_notify_will_save():
            self.purge_changes_async(view)
            # TextDocumentSaveReason.Manual
            self.session.send_notification(will_save(old_file_name, 1))

    def on_post_save_async(self, view: sublime.View) -> None:
        file_name = view.file_name()
        if file_name and file_name != self.file_name:
            self._check_did_close()
            self.file_name = file_name
            self._check_did_open(view)
        else:
            send_did_save, include_text = self.should_notify_did_save()
            if send_did_save:
                self.purge_changes_async(view)
                # mypy: expected sublime.View, got ViewLike
                self.session.send_notification(did_save(view, include_text, self.file_name))
        if self.should_show_diagnostics_panel:
            mgr = self.session.manager()
            if mgr:
                mgr.show_diagnostics_panel_async()

    def some_view(self) -> Optional[sublime.View]:
        for sv in self.session_views:
            return sv.view
        return None

    def on_diagnostics_async(self, raw_diagnostics: List[Diagnostic], version: Optional[int]) -> None:
        data_per_severity = {}  # type: Dict[int, DiagnosticSeverityData]
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
                severity = diagnostic_severity(diagnostic)
                data = data_per_severity.get(severity)
                if data is None:
                    data = DiagnosticSeverityData(severity)
                    data_per_severity[severity] = data
                region = range_to_region(Range.from_lsp(diagnostic["range"]), view)
                data.regions.append(region)
                data.tags = diagnostic.get('tags', [])
                diagnostics.append((diagnostic, region))
                if severity == DiagnosticSeverity.Error:
                    total_errors += 1
                elif severity == DiagnosticSeverity.Warning:
                    total_warnings += 1
                if severity <= userprefs().diagnostics_panel_include_severity_level:
                    data.panel_contribution.append(format_diagnostic_for_panel(diagnostic))
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
        data_per_severity: Dict[int, DiagnosticSeverityData],
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
        data_per_severity: Dict[int, DiagnosticSeverityData],
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
        flags = userprefs().diagnostics_highlight_style_to_add_regions_flag()
        for sv in self.session_views:
            sv.present_diagnostics_async(flags)
        mgr = self.session.manager()
        if mgr:
            mgr.update_diagnostics_panel_async()

    def __str__(self) -> str:
        return '{}:{}:{}'.format(self.session.config.name, self.id, self.file_name)
