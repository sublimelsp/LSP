from .registry import get_position
from .registry import LSPViewEventListener
from .session_view import SessionView
from .sessions import Session
from .typing import Any, Callable, Optional, Dict, Generator, Iterable
from .windows import AbstractViewListener
import sublime
import threading


SUBLIME_WORD_MASK = 515


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


def _clear_async(lock: threading.Lock, session_views: Dict[str, SessionView]) -> Callable[[], None]:

    def run() -> None:
        with lock:
            session_views.clear()

    return run


class DocumentSyncListener(LSPViewEventListener, AbstractViewListener):

    @classmethod
    def applies_to_primary_view_only(cls) -> bool:
        return False

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._file_name = ''
        self._session_views = {}  # type: Dict[str, SessionView]
        self._session_views_lock = threading.Lock()

    def __del__(self) -> None:
        self._clear_async()

    def _clear_async(self) -> None:
        sublime.set_timeout_async(_clear_async(self._session_views_lock, self._session_views))

    def on_session_initialized_async(self, session: Session) -> None:
        assert not self.view.is_loading()
        with self._session_views_lock:
            if session.config.name not in self._session_views:
                self._session_views[session.config.name] = SessionView(self, session)
                self.view.settings().set("lsp_active", True)

    def on_session_shutdown_async(self, session: Session) -> None:
        with self._session_views_lock:
            self._session_views.pop(session.config.name, None)
            if not self._session_views:
                self.view.settings().erase("lsp_active")

    def session_views(self) -> Generator[SessionView, None, None]:
        yield from self._session_views.values()

    def _register_async(self) -> None:
        file_name = self.view.file_name()
        if file_name:
            self._file_name = file_name
            self.manager.register_listener_async(self)

    def _is_regular_view(self) -> bool:
        v = self.view
        # Not from the quick panel (CTRL+P), must have a filename on-disk, and not a special view like a console,
        # output panel or find-in-files panels.
        return not is_transient_view(v) and bool(v.file_name()) and v.element() is None

    def on_load_async(self) -> None:
        if self._is_regular_view():
            self._register_async()

    def on_activated_async(self) -> None:
        if self._is_regular_view() and not self.view.is_loading():
            self._register_async()

    def purge_changes(self) -> None:
        with self._session_views_lock:
            for sv in self.session_views():
                sv.purge_changes()

    def on_text_changed(self, changes: Iterable[sublime.TextChange]) -> None:
        if self.view.is_primary():
            with self._session_views_lock:
                for sv in self.session_views():
                    sv.on_text_changed(changes)

    def on_pre_save(self) -> None:
        with self._session_views_lock:
            for sv in self.session_views():
                sv.on_pre_save()

    def on_post_save(self) -> None:
        if self.view.file_name() != self._file_name:
            self._file_name = ''
            self._clear_async()
            sublime.set_timeout_async(self._register_async)
            return
        with self._session_views_lock:
            for sv in self.session_views():
                sv.on_post_save()

    def on_close(self) -> None:
        self._clear_async()

    def on_query_context(self, key: str, operator: str, operand: Any, match_all: bool) -> bool:
        capability_prefix = "lsp.capabilities."
        if key.startswith(capability_prefix):
            return isinstance(self.view.settings().get(key[len(capability_prefix):]), dict)
        elif key in ("lsp.sessions", "setting.lsp_active"):
            return bool(self._session_views)
        else:
            return False

    def __str__(self) -> str:
        return str(self.view.id())
