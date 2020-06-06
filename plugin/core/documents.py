from .registry import get_position
from .registry import LSPViewEventListener
from .session_view import SessionView
from .sessions import Session
from .typing import Any, Optional, Dict, Generator, Iterable
from .windows import AbstractViewListener
import sublime


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


class DocumentSyncListener(LSPViewEventListener, AbstractViewListener):

    @classmethod
    def applies_to_primary_view_only(cls) -> bool:
        return False

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._registered = False
        self._session_views = {}  # type: Dict[str, SessionView]

    def on_session_initialized(self, session: Session) -> None:
        assert not self.view.is_loading()
        if session.config.name not in self._session_views:
            self._session_views[session.config.name] = SessionView(self, session)

    def on_session_shutdown(self, session: Session) -> None:
        self._session_views.pop(session.config.name, None)

    def session_views(self) -> Generator[SessionView, None, None]:
        yield from self._session_views.values()

    def on_activated(self) -> None:
        assert not self.view.is_loading()
        if self.view.file_name() and self.view.element() is None:
            self.manager.register_listener(self)
            self._registered = True

    def purge_changes(self) -> None:
        if self._registered:
            for sv in self.session_views():
                sv.purge_changes()

    def on_text_changed(self, changes: Iterable[sublime.TextChange]) -> None:
        if self._registered:
            for sv in self.session_views():
                sv.on_text_changed(changes)

    def on_pre_save(self) -> None:
        if self._registered:
            for sv in self.session_views():
                sv.on_pre_save()

    def on_post_save(self) -> None:
        if self._registered:
            for sv in self.session_views():
                sv.on_post_save()

    def on_close(self) -> None:
        if self._registered and self.view.is_primary():
            self._session_views.clear()
            self.manager.unregister_listener(self)

    def on_query_context(self, key: str, operator: str, operand: Any, match_all: bool) -> bool:
        capability_prefix = "lsp.capabilities."
        if key.startswith(capability_prefix):
            return isinstance(self.view.settings().get(key[len(capability_prefix):]), dict)
        elif key in ("lsp.sessions", "setting.lsp_active"):
            return bool(self._session_views)
        else:
            return False

    def __hash__(self) -> int:
        return hash(id(self))

    def __str__(self) -> str:
        return str(self.view.id())
