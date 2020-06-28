from .core.protocol import TextDocumentSyncKindFull
from .core.protocol import TextDocumentSyncKindNone
from .core.sessions import SessionViewProtocol
from .core.settings import settings
from .core.types import debounced
from .core.typing import Any, Iterable, Optional, List, Dict
from .core.views import did_change
from .core.views import did_close
from .core.views import did_open
from .core.views import did_save
from .core.views import will_save
from weakref import WeakSet
import sublime


class PendingChanges:

    __slots__ = ('version', 'changes')

    def __init__(self, version: int, changes: Iterable[sublime.TextChange]) -> None:
        self.version = version
        self.changes = list(changes)

    def update(self, version: int, changes: Iterable[sublime.TextChange]) -> None:
        self.version = version
        self.changes.extend(changes)


class SessionBuffer:
    """
    Holds state per session per buffer.

    It stores the filename, handles document synchronization for the buffer.

    TODO: Move diagnostics storage to this class.
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

    def __del__(self) -> None:
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
        self._massive_hack_changed()

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
            self._massive_hack_changed()

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
        self._massive_hack_saved()

    def on_diagnostics_async(self, diagnostics: List[Dict[str, Any]], version: Optional[int]) -> None:
        # TODO: Store diagnostics here.
        pass

    def _massive_hack_changed(self) -> None:
        if settings.auto_show_diagnostics_panel == 'saved':
            # TODO: This method should disappear
            for sv in self.session_views:
                listener = sv.listener()
                if listener:
                    diagnostics = listener.manager.diagnostics._updatable
                    if diagnostics:
                        diagnostics.on_document_changed()  # type: ignore

    def _massive_hack_saved(self) -> None:
        if settings.auto_show_diagnostics_panel == 'saved':
            # TODO: This method should disappear
            for sv in self.session_views:
                listener = sv.listener()
                if listener:
                    diagnostics = listener.manager.diagnostics._updatable
                    if diagnostics:
                        diagnostics.on_document_saved()  # type: ignore

    def __str__(self) -> str:
        return '{}:{}:{}'.format(self.session.config.name, self.id, self.file_name)
