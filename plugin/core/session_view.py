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
from .windows import AbstractViewListener
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
        session.register_session_view(self)
        self.view.set_status(self.status_key, session.config.name)
        self._add_self_to_setting("lsp_active")
        settings = self.view.settings()
        # TODO: Language ID must be UNIQUE!
        languages = settings.get("lsp_language")
        language_id = ''
        if not isinstance(languages, dict):
            languages = {}
        for language in session.config.languages:
            if language.match_document(view2scope(self.view)):
                languages[session.config.name] = language.id
                language_id = language.id
                break
        settings.set("lsp_language", languages)
        if self.session.should_notify_did_open():
            # mypy: expected sublime.View, got ViewLike
            self.session.send_notification(did_open(self.view, language_id))  # type: ignore
        for capability in self.session.capabilities.toplevel_keys():
            if capability.endswith('Provider'):
                self.register_capability(capability)

    def __del__(self) -> None:
        for capability in self.session.capabilities.toplevel_keys():
            if capability.endswith('Provider'):
                self.unregister_capability(capability)
        if not self.session.exiting:
            if self.session.should_notify_did_close():
                self.session.send_notification(did_close(self.view))  # type: ignore
            self.session.unregister_session_view(self)
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
        self._discard_self_from_setting("lsp_active")

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

    def shutdown(self) -> None:
        listener = self.listener()
        if listener:
            listener.on_session_shutdown(self.session)

    def did_change(self, changes: Iterable[sublime.TextChange]) -> None:
        sync_kind = self.session.text_sync_kind()
        if sync_kind == TextDocumentSyncKindNone:
            return
        c = None if sync_kind == TextDocumentSyncKindFull else changes
        notification = did_change(self.view, c)  # type: ignore
        self.session.send_notification(notification)
        self._massive_hack_changed()

    def will_save(self, reason: int) -> None:
        if self.session.should_notify_will_save():
            # mypy: expected sublime.View, got ViewLike
            self.session.send_notification(will_save(self.view, reason))  # type: ignore

    def did_save(self) -> None:
        send_did_save, include_text = self.session.should_notify_did_save()
        if send_did_save:
            # mypy: expected sublime.View, got ViewLike
            self.session.send_notification(did_save(self.view, include_text))  # type: ignore
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
