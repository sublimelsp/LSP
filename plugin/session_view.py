from .core.protocol import Diagnostic
from .core.sessions import Session
from .core.types import view2scope
from .core.typing import Iterable, List, Tuple
from .core.windows import AbstractViewListener
from .session_buffer import SessionBuffer
from weakref import WeakValueDictionary
from weakref import ref
import sublime


class SessionView:
    """
    Holds state per session per view.
    """

    LANGUAGE_ID_KEY = "lsp_language"

    _session_buffers = WeakValueDictionary()  # type: WeakValueDictionary[Tuple[str, int], SessionBuffer]

    def __init__(self, listener: AbstractViewListener, session: Session) -> None:
        self.view = listener.view
        self.session = session
        settings = self.view.settings()
        # TODO: Language ID must be UNIQUE!
        languages = settings.get(self.LANGUAGE_ID_KEY)
        self._language_id = ''
        if not isinstance(languages, dict):
            languages = {}
        for language in session.config.languages:
            if language.match_scope(view2scope(self.view)):
                languages[session.config.name] = language.id
                self._language_id = language.id
                break
        settings.set(self.LANGUAGE_ID_KEY, languages)
        buffer_id = self.view.buffer_id()
        key = (session.config.name, buffer_id)
        session_buffer = self._session_buffers.get(key)
        if session_buffer is None:
            session_buffer = SessionBuffer(self, buffer_id, self._language_id)
            self._session_buffers[key] = session_buffer
        else:
            session_buffer.add_session_view(self)
        self.session_buffer = session_buffer
        self.listener = ref(listener)
        session.register_session_view_async(self)
        session.config.set_view_status(self.view, "")
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
            self.session.unregister_session_view_async(self)
        self.session.config.erase_view_status(self.view)
        settings = self.view.settings()  # type: sublime.Settings
        # TODO: Language ID must be UNIQUE!
        languages = settings.get(self.LANGUAGE_ID_KEY)
        if isinstance(languages, dict):
            languages.pop(self.session.config.name, None)
            if languages:
                settings.set(self.LANGUAGE_ID_KEY, languages)
            else:
                settings.erase(self.LANGUAGE_ID_KEY)

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

    def present_diagnostics_async(self, diagnostics: List[Diagnostic]) -> None:
        # TODO: Present diagnostics here.
        pass

    def on_text_changed(self, changes: Iterable[sublime.TextChange]) -> None:
        self.session_buffer.on_text_changed(changes)

    def purge_changes(self) -> None:
        self.session_buffer.purge_changes()

    def on_pre_save(self) -> None:
        self.session_buffer.on_pre_save()

    def on_post_save(self) -> None:
        self.session_buffer.on_post_save()

    def __str__(self) -> str:
        return '{}:{}'.format(self.session.config.name, self.view.id())
