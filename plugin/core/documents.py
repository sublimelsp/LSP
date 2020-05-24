from .registry import LSPViewEventListener
from .session_view import PendingBuffer
from .session_view import SessionView
from .sessions import Session
from .typing import Optional, Dict, Generator, Iterable
import sublime


SUBLIME_WORD_MASK = 515


def get_position(view: sublime.View, event: Optional[dict] = None) -> int:
    if event:
        return view.window_to_text((event["x"], event["y"]))
    else:
        return view.sel()[0].begin()


def is_at_word(view: sublime.View, event: Optional[dict]) -> bool:
    pos = get_position(view, event)
    return position_is_word(view, pos)


def position_is_word(view: sublime.View, position: int) -> bool:
    point_classification = view.classify(position)
    if point_classification & SUBLIME_WORD_MASK:
        return True
    else:
        return False


def is_transient_view(view: sublime.View) -> bool:
    window = view.window()
    if window:
        if window.get_view_index(view)[1] == -1:
            return True  # Quick panel transient views
        return view == window.transient_view_in_group(window.active_group())
    else:
        return True


class DocumentSyncListener(LSPViewEventListener):

    @classmethod
    def is_applicable(cls, view_settings: dict) -> bool:
        return cls.has_supported_syntax(view_settings)

    @classmethod
    def applies_to_primary_view_only(cls) -> bool:
        return False

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._registered = False
        self._session_views = {}  # type: Dict[str, SessionView]
        self._pending_buffer = None  # type: Optional[PendingBuffer]

    def __del__(self) -> None:
        self.view.settings().erase("lsp_active")

    def on_session_initialized(self, session: Session) -> None:
        if session.config.name not in self._session_views:
            self._session_views[session.config.name] = SessionView(self, session)

    def on_session_shutdown(self, session: Session) -> None:
        self._session_views.pop(session.config.name, None)

    def session_views(self) -> Generator[SessionView, None, None]:
        yield from self._session_views.values()

    def on_load(self) -> None:
        # skip transient views:
        if not is_transient_view(self.view):
            self._register()

    def on_activated(self) -> None:
        if self.view.file_name() and not is_transient_view(self.view):
            self._register()

    def on_text_changed(self, changes: Iterable[sublime.TextChange]) -> None:
        change_count = self.view.change_count()
        if self._pending_buffer is None:
            self._pending_buffer = PendingBuffer(change_count, changes)
        else:
            self._pending_buffer.update(change_count, changes)
        sublime.set_timeout(lambda: self._purge_did_change(change_count), 500)

    def on_pre_save(self) -> None:
        if self.view.file_name():
            for sv in self.session_views():
                sv.will_save(reason=1)  # TextDocumentSaveReason.Manual

    def on_post_save(self) -> None:
        self.purge_changes()
        for sv in self.session_views():
            sv.did_save()

    def on_close(self) -> None:
        if self.view.file_name() and self.view.is_primary() and self.has_manager():
            self._session_views.clear()
            if self._registered:
                self.manager.unregister_listener(self)

    def _purge_did_change(self, change_count: int) -> None:
        if change_count == self.view.change_count():
            self.purge_changes()

    def purge_changes(self) -> None:
        if self._pending_buffer is not None:
            for sv in self.session_views():
                sv.did_change(self._pending_buffer.changes)
            self._pending_buffer = None

    def _register(self) -> None:
        if not self._registered:
            self.manager.register_listener(self)
            self.view.settings().set("lsp_active", True)
            self._registered = True

    def __hash__(self) -> int:
        return hash(id(self))

    def __str__(self) -> str:
        return str(self.view.id())
