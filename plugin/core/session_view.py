from .protocol import TextDocumentSyncKindNone, TextDocumentSyncKindFull
from .sessions import Session
from .settings import settings
from .types import view2scope
from .typing import Any, Iterable
from .views import did_change
from .views import did_close
from .views import did_open
from .views import did_save
from .views import will_save
from .windows import ViewListenerProtocol
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

    def __init__(self, listener: ViewListenerProtocol, session: Session) -> None:
        self.view = listener.view
        self.session = session
        self.listener = weakref.ref(listener)
        session.register_session_view(self)
        self.view.set_status(self.status_key, session.config.name)
        settings = self.view.settings()
        # TODO: Language ID must be UNIQUE!
        languages = settings.get("lsp_language")
        if not isinstance(languages, dict):
            languages = {}
        for language in session.config.languages:
            if language.match_document(view2scope(self.view)):
                languages[session.config.name] = language.id
                break
        settings.set("lsp_language", languages)
        if self.session.should_notify_did_open():
            language_id = self.view.settings().get("lsp_language", "TODO")
            if self.session.client:
                # mypy: expected sublime.View, got ViewLike
                self.session.client.send_notification(did_open(self.view, language_id))  # type: ignore

    def __del__(self) -> None:
        if self.session.client and not self.session.client.exiting and self.session.should_notify_did_close():
            self.session.client.send_notification(did_close(self.view))  # type: ignore
        self.view.erase_status(self.status_key)
        settings = self.view.settings()  # type: sublime.Settings
        # TODO: Language ID must be UNIQUE!
        languages = settings.get("lsp_language")
        if isinstance(languages, dict):
            languages.pop(self.session.config.name, None)
            if languages:
                settings.set("lsp_language", languages)
            else:
                settings.erase("lsp_language")
        if not self.session.client.exiting:
            self.session.unregister_session_view(self)

    def did_change(self, changes: Iterable[sublime.TextChange]) -> None:
        sync_kind = self.session.text_sync_kind()
        if sync_kind == TextDocumentSyncKindNone:
            return
        c = None if sync_kind == TextDocumentSyncKindFull else changes
        notification = did_change(self.view, c)  # type: ignore
        self.session.client.send_notification(notification)
        self._massive_hack_changed()

    def will_save(self, reason: int) -> None:
        if self.session.client and self.session.should_notify_will_save():
            # mypy: expected sublime.View, got ViewLike
            self.session.client.send_notification(will_save(self.view, reason))  # type: ignore

    def did_save(self) -> None:
        if self.session.client:
            send_did_save, include_text = self.session.should_notify_did_save()
            if send_did_save:
                # mypy: expected sublime.View, got ViewLike
                self.session.client.send_notification(did_save(self.view, include_text))  # type: ignore
        self._massive_hack_saved()

    def on_diagnostics(self, diagnostics: Any) -> None:
        pass  # TODO

    @property
    def status_key(self) -> str:
        return "lsp_{}".format(self.session.config.name)

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

    def __hash__(self) -> int:
        return hash(id(self))

    def __str__(self) -> str:
        return '{}-{}'.format(self.view.id(), self.session.config.name)
