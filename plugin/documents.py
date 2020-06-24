from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LSPViewEventListener
from .core.sessions import Session
from .core.settings import settings as global_settings
from .core.types import debounced
from .core.typing import Any, Callable, Optional, Dict, Generator, Iterable
from .core.views import document_color_params
from .core.views import lsp_color_to_phantom
from .core.windows import AbstractViewListener
from .save_command import LspSaveCommand
from .session_buffer import SessionBuffer
from .session_view import SessionView
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
        self._session_views = {}  # type: Dict[str, SessionView]
        self._session_views_lock = threading.Lock()
        self._stored_point = -1
        self._color_phantoms = sublime.PhantomSet(self.view, "lsp_color")

    def __del__(self) -> None:
        self._stored_point = -1  # Prevent a debounced request to alter the phantoms again
        self._color_phantoms.update([])
        self._clear_async()

    # --- Implements AbstractViewListener ------------------------------------------------------------------------------

    def on_session_initialized_async(self, session: Session) -> None:
        assert not self.view.is_loading()
        added = False
        with self._session_views_lock:
            if session.config.name not in self._session_views:
                self._session_views[session.config.name] = SessionView(self, session)
                self.view.settings().set("lsp_active", True)
                added = True
        if added and "colorProvider" not in global_settings.disabled_capabilities:
            self._do_color_boxes_async()

    def on_session_shutdown_async(self, session: Session) -> None:
        with self._session_views_lock:
            self._session_views.pop(session.config.name, None)
            if not self._session_views:
                self.view.settings().erase("lsp_active")

    def session_views(self) -> Generator[SessionView, None, None]:
        yield from self._session_views.values()

    def session_buffers(self) -> Generator[SessionBuffer, None, None]:
        for sv in self.session_views():
            yield sv.session_buffer

    # --- Callbacks from Sublime Text ----------------------------------------------------------------------------------

    def on_load_async(self) -> None:
        if self._is_regular_view():
            self._register_async()

    def on_activated_async(self) -> None:
        if self._is_regular_view() and not self.view.is_loading():
            self._register_async()

    def on_modified_async(self) -> None:
        sel = self.view.sel()
        if len(sel) < 1:
            return
        current_point = sel[0].b
        if self._stored_point != current_point:
            self._stored_point = current_point
            if "colorProvider" not in global_settings.disabled_capabilities:
                self._when_selection_remains_stable_async(self._do_color_boxes_async, current_point, after_ms=800)

    def on_text_changed(self, changes: Iterable[sublime.TextChange]) -> None:
        if self.view.is_primary():
            with self._session_views_lock:
                for sv in self.session_views():
                    sv.on_text_changed(changes)

    def on_revert(self) -> None:
        if self.view.is_primary():
            with self._session_views_lock:
                for sv in self.session_views():
                    sv.on_revert()

    def on_reload(self) -> None:
        if self.view.is_primary():
            with self._session_views_lock:
                for sv in self.session_views():
                    sv.on_reload()

    def on_pre_save(self) -> None:
        if self.view.is_primary():
            view_settings = self.view.settings()
            if view_settings.has(LspSaveCommand.SKIP_ON_PRE_SAVE_KEY):
                view_settings.erase(LspSaveCommand.SKIP_ON_PRE_SAVE_KEY)
                return
            with self._session_views_lock:
                for sv in self.session_views():
                    sv.on_pre_save()

    def on_post_save(self) -> None:
        if self.view.is_primary():
            with self._session_views_lock:
                for sv in self.session_views():
                    sv.on_post_save()

    def on_close(self) -> None:
        self._clear_async()

    def on_query_context(self, key: str, operator: int, operand: Any, match_all: bool) -> bool:
        if key == "lsp.session_with_capability" and operator == sublime.OP_EQUAL and isinstance(operand, str):
            capabilities = [s.strip() for s in operand.split("|")]
            get = self.view.settings().get
            for capability in capabilities:
                if isinstance(get(capability), dict):
                    return True
            return False
        elif key in ("lsp.sessions", "setting.lsp_active"):
            return bool(self._session_views)
        else:
            return False

    def on_hover(self, point: int, hover_zone: int) -> None:
        if (hover_zone != sublime.HOVER_TEXT
                or self.view.is_popup_visible()
                or "hover" in global_settings.disabled_capabilities):
            return
        self.view.run_command("lsp_hover", {"point": point})

    # --- textDocument/documentColor -----------------------------------------------------------------------------------

    def _do_color_boxes_async(self) -> None:
        session = self.session("colorProvider")
        if session:
            session.send_request(Request.documentColor(document_color_params(self.view)), self._on_color_boxes)

    def _on_color_boxes(self, response: Any) -> None:
        color_infos = response if response else []
        self._color_phantoms.update([lsp_color_to_phantom(self.view, color_info) for color_info in color_infos])

    # --- Utility methods ----------------------------------------------------------------------------------------------

    def purge_changes(self) -> None:
        with self._session_views_lock:
            for sv in self.session_views():
                sv.purge_changes()

    def _when_selection_remains_stable_async(self, f: Callable[[], None], pt: int, after_ms: int) -> None:
        debounced(f, after_ms, lambda: self._stored_point == pt, async_thread=True)

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

    def _clear_async(self) -> None:
        sublime.set_timeout_async(_clear_async(self._session_views_lock, self._session_views))

    def __str__(self) -> str:
        return str(self.view.id())
