from .core.logging import debug
from .core.protocol import TextDocumentSyncKindNone, TextDocumentSyncKindFull
from .core.sessions import Session
from .core.settings import settings
from .core.types import debounced
from .core.types import view2scope
from .core.typing import Any, Iterable, Optional
from .core.views import did_change
from .core.views import did_close
from .core.views import did_open
from .core.views import did_save
from .core.views import will_save
from .core.windows import AbstractViewListener
import sublime
import weakref


class PendingBuffer:

    __slots__ = ('version', 'changes')

    def __init__(self, version: int, changes: Iterable[sublime.TextChange]) -> None:
        self.version = version
        self.changes = list(changes)

    def update(self, version: int, changes: Iterable[sublime.TextChange]) -> None:
        self.version = version
        self.changes.extend(changes)


class SessionView:

    def __init__(self, listener: AbstractViewListener, session: Session) -> None:
        self.view = listener.view
        self.session = session
        self.listener = weakref.ref(listener)
        self._file_name = self.view.file_name() or ""
        if not self._file_name:
            raise ValueError("missing filename")
        self._buffer_id = self.view.buffer_id()
        if self._buffer_id == 0:
            raise ValueError("missing buffer ID")
        self._pending_buffer = None  # type: Optional[PendingBuffer]
        session.register_session_view_async(self)
        session.config.set_view_status(self.view, "")
        settings = self.view.settings()
        # TODO: Language ID must be UNIQUE!
        languages = settings.get("lsp_language")
        self._language_id = ''
        if not isinstance(languages, dict):
            languages = {}
        for language in session.config.languages:
            if language.match_scope(view2scope(self.view)):
                languages[session.config.name] = language.id
                self._language_id = language.id
                break
        settings.set("lsp_language", languages)
        if self.view.is_primary() and self.session.should_notify_did_open():
            self.session.send_notification(did_open(self.view, self._language_id))
        for capability in self.session.capabilities.toplevel_keys():
            if capability.endswith('Provider'):
                self.register_capability(capability)

    def __del__(self) -> None:
        for capability in self.session.capabilities.toplevel_keys():
            if capability.endswith('Provider'):
                self.unregister_capability(capability)
        # If the session is exiting then there's no point in sending textDocument/didClose and there's also no point
        # in unregistering ourselves from the session.
        if not self.session.exiting:
            # Only send textDocument/didClose when we are the only view left (i.e. there are no other clones).
            if self.session.should_notify_did_close() and not self._has_clones():
                self.session.send_notification(did_close(self._file_name))
            self.session.unregister_session_view_async(self)
        self.session.config.erase_view_status(self.view)
        settings = self.view.settings()  # type: sublime.Settings
        # TODO: Language ID must be UNIQUE!
        languages = settings.get("lsp_language")
        if isinstance(languages, dict):
            languages.pop(self.session.config.name, None)
            if languages:
                settings.set("lsp_language", languages)
            else:
                settings.erase("lsp_language")

    def register_capability(self, capability: str) -> None:
        self._add_self_to_setting(capability)
        if capability == 'hoverProvider':
            # TODO: Remember the old value? Detect changes to show_definitions?
            self.view.settings().set('show_definitions', False)

    def unregister_capability(self, capability: str) -> None:
        if self._discard_self_from_setting(capability) and capability == 'hoverProvider':
            # TODO: Remember the old value? Detect changes to show_definitions?
            self.view.settings().set('show_definitions', True)

    def _add_self_to_setting(self, key: str) -> None:
        settings = self.view.settings()
        value = settings.get(key)
        if isinstance(value, dict):
            value[self.session.config.name] = None
        else:
            value = {self.session.config.name: None}
        settings.set(key, value)

    def _discard_self_from_setting(self, key: str) -> bool:
        """Returns True when the setting was erased, otherwise False."""
        settings = self.view.settings()
        value = settings.get(key)
        if isinstance(value, dict):
            value.pop(self.session.config.name, None)
        if value:
            settings.set(key, value)
            return False
        else:
            settings.erase(key)
            return True

    def shutdown_async(self) -> None:
        listener = self.listener()
        if listener:
            listener.on_session_shutdown_async(self.session)

    def on_text_changed(self, changes: Iterable[sublime.TextChange]) -> None:
        last_change = list(changes)[-1]
        if last_change.a.pt == 0 and last_change.b.pt == 0 and last_change.str == '' and self.view.size() != 0:
            # Issue https://github.com/sublimehq/sublime_text/issues/3323
            # A special situation when changes externally. We receive two changes,
            # one that removes all content and one that has 0,0,'' parameters. We resend whole
            # file in that case to fix broken state.
            debug('Working around the on_text_changed bug {}'.format(self.view.file_name()))
            self.purge_changes()
            notification = did_change(self.view, None)  # type: ignore
            self.session.send_notification(notification)
            self._massive_hack_changed()
        else:
            change_count = self.view.change_count()
            if self._pending_buffer is None:
                self._pending_buffer = PendingBuffer(change_count, changes)
            else:
                self._pending_buffer.update(change_count, changes)
            debounced(self.purge_changes, 500,
                      lambda: self.view.is_valid() and change_count == self.view.change_count())

    def purge_changes(self) -> None:
        if self._pending_buffer is not None:
            sync_kind = self.session.text_sync_kind()
            if sync_kind == TextDocumentSyncKindNone:
                return
            c = None if sync_kind == TextDocumentSyncKindFull else self._pending_buffer.changes
            notification = did_change(self.view, c)  # type: ignore
            self.session.send_notification(notification)
            self._pending_buffer = None
            self._massive_hack_changed()

    def on_pre_save(self) -> None:
        if self.session.should_notify_will_save():
            self.purge_changes()
            # mypy: expected sublime.View, got ViewLike
            # TextDocumentSaveReason.Manual
            self.session.send_notification(will_save(self.view, 1))  # type: ignore

    def on_post_save(self) -> None:
        send_did_save, include_text = self.session.should_notify_did_save()
        if send_did_save:
            self.purge_changes()
            # mypy: expected sublime.View, got ViewLike
            self.session.send_notification(did_save(self.view, include_text, self._file_name))  # type: ignore
        self._massive_hack_saved()

    def on_diagnostics(self, diagnostics: Any) -> None:
        pass  # TODO

    def _has_clones(self) -> bool:
        # TODO: Maybe listen for the "clone_file" command and do some bookkeeping? This is currently an O(N) algorithm.
        try:
            views = self.session.window.views()
            view_id = self.view.id()
            for view in views:
                if view.id() != view_id:
                    if view.buffer_id() == self._buffer_id:
                        return True
        except AttributeError:
            pass
        return False

    def _massive_hack_changed(self) -> None:
        if settings.auto_show_diagnostics_panel == 'saved':
            # TODO: This method should disappear
            listener = self.listener()
            if listener:
                mgr = listener.manager  # type: ignore
                mgr.diagnostics._updatable.on_document_changed()  # type: ignore

    def _massive_hack_saved(self) -> None:
        if settings.auto_show_diagnostics_panel == 'saved':
            # TODO: This method should disappear
            listener = self.listener()
            if listener:
                mgr = listener.manager  # type: ignore
                mgr.diagnostics._updatable.on_document_saved()  # type: ignore

    def __str__(self) -> str:
        return '{}-{}'.format(self.view.id(), self.session.config.name)
