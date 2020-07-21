from .core.protocol import Diagnostic
from .core.protocol import DiagnosticSeverity
from .core.protocol import TextDocumentSyncKindFull
from .core.protocol import TextDocumentSyncKindNone
from .core.sessions import SessionViewProtocol
from .core.settings import settings
from .core.types import debounced
from .core.typing import Any, Iterable, Optional, List, Dict
from .core.views import DIAGNOSTIC_SEVERITY
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

    __slots__ = ('regions', 'annotations', 'panel_contribution', 'scope', 'icon')

    def __init__(self, severity: int) -> None:
        self.regions = []  # type: List[sublime.Region]
        self.annotations = []  # type: List[str]
        self.panel_contribution = []  # type: List[str]
        _, __, self.scope, self.icon = DIAGNOSTIC_SEVERITY[severity - 1]
        if settings.diagnostics_gutter_marker != "sign":
            self.icon = settings.diagnostics_gutter_marker


class SessionBuffer:
    """
    Holds state per session per buffer.

    It stores the filename, handles document synchronization for the buffer, and stores/receives diagnostics.
    """

    def __init__(self, session_view: SessionViewProtocol, buffer_id: int, language_id: str) -> None:
        self.view = session_view.view
        self.session = session_view.session
        self.session_views = WeakSet()  # type: WeakSet[SessionViewProtocol]
        self.session_views.add(session_view)
        file_name = self.view.file_name()
        if not file_name:
            raise ValueError("missing filename")
        self.file_name = file_name
        self.id = buffer_id
        self.pending_changes = None  # type: Optional[PendingChanges]
        if self.session.should_notify_did_open():
            self.session.send_notification(did_open(self.view, language_id))
        self.session.register_session_buffer_async(self)
        self.diagnostics = []  # type: List[Diagnostic]
        self.data_per_severity = {}  # type: Dict[int, DiagnosticSeverityData]
        self.diagnostics_version = -1
        self.diagnostics_flags = 0
        self.diagnostics_are_visible = False
        self.last_text_change_time = 0.0
        self.total_errors = 0
        self.total_warnings = 0
        self.should_show_diagnostics_panel = False

    def __del__(self) -> None:
        mgr = self.session.manager()
        if mgr:
            mgr.update_diagnostics_panel_async()
        # If the session is exiting then there's no point in sending textDocument/didClose and there's also no point
        # in unregistering ourselves from the session.
        if not self.session.exiting:
            # Only send textDocument/didClose when we are the only view left (i.e. there are no other clones).
            if self.session.should_notify_did_close():
                self.session.send_notification(did_close(self.file_name))
            self.session.unregister_session_buffer_async(self)

    def add_session_view(self, sv: SessionViewProtocol) -> None:
        self.session_views.add(sv)

    def shutdown_async(self) -> None:
        for sv in self.session_views:
            listener = sv.listener()
            if listener:
                listener.on_session_shutdown_async(self.session)

    def on_text_changed_async(self, changes: Iterable[sublime.TextChange]) -> None:
        self.last_text_change_time = time.time()
        last_change = list(changes)[-1]
        if last_change.a.pt == 0 and last_change.b.pt == 0 and last_change.str == '' and self.view.size() != 0:
            # Issue https://github.com/sublimehq/sublime_text/issues/3323
            # A special situation when changes externally. We receive two changes,
            # one that removes all content and one that has 0,0,'' parameters.
            pass
        else:
            change_count = self.view.change_count()
            if self.pending_changes is None:
                self.pending_changes = PendingChanges(change_count, changes)
            else:
                self.pending_changes.update(change_count, changes)
            debounced(self.purge_changes_async, 500,
                      lambda: self.view.is_valid() and change_count == self.view.change_count())

    def on_revert_async(self) -> None:
        self.pending_changes = None  # Don't bother with pending changes
        self.session.send_notification(did_change(self.view, None))

    on_reload_async = on_revert_async

    def purge_changes_async(self) -> None:
        if self.pending_changes is not None:
            sync_kind = self.session.text_sync_kind()
            if sync_kind == TextDocumentSyncKindNone:
                return
            c = None if sync_kind == TextDocumentSyncKindFull else self.pending_changes.changes
            notification = did_change(self.view, c)
            self.session.send_notification(notification)
            self.pending_changes = None

    def on_pre_save_async(self, old_file_name: str) -> None:
        if self.session.should_notify_will_save():
            self.purge_changes_async()
            # TextDocumentSaveReason.Manual
            self.session.send_notification(will_save(old_file_name, 1))

    def on_post_save_async(self) -> None:
        file_name = self.view.file_name()
        if file_name and file_name != self.file_name:
            if self.session.should_notify_did_close():
                self.session.send_notification(did_close(self.file_name))
            self.file_name = file_name
            if self.session.should_notify_did_open():
                # TODO: Language ID should be UNIQUE!
                language_ids = self.view.settings().get("lsp_language")
                if isinstance(language_ids, dict):
                    for config_name, language_id in language_ids.items():
                        if config_name == self.session.config.name:
                            self.session.send_notification(did_open(self.view, language_id))
                            break
        else:
            send_did_save, include_text = self.session.should_notify_did_save()
            if send_did_save:
                self.purge_changes_async()
                # mypy: expected sublime.View, got ViewLike
                self.session.send_notification(did_save(self.view, include_text, self.file_name))
        if settings.show_diagnostics_panel_on_save():
            if self.should_show_diagnostics_panel:
                mgr = self.session.manager()
                if mgr:
                    mgr.show_diagnostics_panel_async()

    def on_diagnostics_async(self, raw_diagnostics: List[Dict[str, Any]], version: Optional[int]) -> None:
        diagnostics = []  # type: List[Diagnostic]
        data_per_severity = {}  # type: Dict[int, DiagnosticSeverityData]
        total_errors = 0
        total_warnings = 0
        should_show_diagnostics_panel = False
        change_count = self.view.change_count()
        if version is None:
            version = change_count
        if version == change_count:
            diagnostics_version = version
            for index, diagnostic in enumerate(map(Diagnostic.from_lsp, raw_diagnostics)):
                diagnostics.append(diagnostic)
                data = data_per_severity.get(diagnostic.severity)
                if data is None:
                    data = DiagnosticSeverityData(diagnostic.severity)
                    data_per_severity[diagnostic.severity] = data
                data.regions.append(range_to_region(diagnostic.range, self.view))
                if diagnostic.severity == DiagnosticSeverity.Error:
                    total_errors += 1
                elif diagnostic.severity == DiagnosticSeverity.Warning:
                    total_warnings += 1
                if diagnostic.severity <= settings.diagnostics_panel_include_severity_level:
                    data.panel_contribution.append(format_diagnostic_for_panel(diagnostic))
                if diagnostic.severity <= settings.auto_show_diagnostics_panel_level:
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
        diagnostics: List[Diagnostic],
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

        if not bool(diagnostics) and not self.diagnostics_are_visible:
            # Nothing was previously visible, and nothing will become visible. So do nothing.
            pass
        elif self.diagnostics_are_visible:
            # Old diagnostics are visible. Update immediately.
            present()
        else:
            # There were no diagnostics visible before. Show them a bit later.
            delay_in_seconds = settings.diagnostics_delay_ms / 1000.0 + self.last_text_change_time - time.time()
            if self.view.is_auto_complete_visible():
                delay_in_seconds += settings.diagnostics_additional_delay_auto_complete_ms / 1000.0
            if delay_in_seconds <= 0.0:
                present()
            else:
                debounced(
                    present,
                    timeout_ms=int(1000.0 * delay_in_seconds),
                    condition=lambda: self.view.is_valid() and self.view.change_count() == diagnostics_version,
                    async_thread=True
                )

    def _present_diagnostics_async(
        self,
        diagnostics_version: int,
        diagnostics: List[Diagnostic],
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
        flags = settings.diagnostics_highlight_style_to_add_regions_flag()
        for sv in self.session_views:
            sv.present_diagnostics_async(flags)
        mgr = self.session.manager()
        if mgr:
            mgr.update_diagnostics_panel_async()
            if not self.should_show_diagnostics_panel:
                mgr.hide_diagnostics_panel_async()
            elif settings.show_diagnostics_panel_always():
                mgr.show_diagnostics_panel_async()

    def __str__(self) -> str:
        return '{}:{}:{}'.format(self.session.config.name, self.id, self.file_name)
