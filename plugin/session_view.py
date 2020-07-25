from .core.protocol import Diagnostic
from .core.protocol import Range
from .core.sessions import Session
from .core.settings import settings as global_settings
from .core.types import view2scope
from .core.typing import Any, Iterable, List, Tuple
from .core.views import DIAGNOSTIC_SEVERITY
from .core.views import format_diagnostic_for_annotation
from .core.views import range_to_region
from .core.windows import AbstractViewListener
from .session_buffer import SessionBuffer
from weakref import ref
from weakref import WeakValueDictionary
import sublime


class SessionView:
    """
    Holds state per session per view.
    """

    LANGUAGE_ID_KEY = "lsp_language"
    SHOW_DEFINITIONS_KEY = "show_definitions"
    HOVER_PROVIDER_KEY = "hoverProvider"
    HOVER_PROVIDER_COUNT_KEY = "lsp_hover_provider_count"

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
        if self.session.has_capability(self.HOVER_PROVIDER_KEY):
            self._increment_hover_count()

    def __del__(self) -> None:
        if self.session.has_capability(self.HOVER_PROVIDER_KEY):
            self._decrement_hover_count()
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
        for severity in range(1, len(DIAGNOSTIC_SEVERITY) + 1):
            self.view.erase_regions(self.diagnostics_key(severity))

    def _increment_hover_count(self) -> None:
        settings = self.view.settings()
        count = settings.get(self.HOVER_PROVIDER_COUNT_KEY, 0)
        if isinstance(count, int):
            count += 1
            settings.set(self.HOVER_PROVIDER_COUNT_KEY, count)
            settings.set(self.SHOW_DEFINITIONS_KEY, False)

    def _decrement_hover_count(self) -> None:
        settings = self.view.settings()
        count = settings.get(self.HOVER_PROVIDER_COUNT_KEY)
        if isinstance(count, int):
            count -= 1
            if count == 0:
                settings.erase(self.HOVER_PROVIDER_COUNT_KEY)
                settings.set(self.SHOW_DEFINITIONS_KEY, True)

    def register_capability_async(self, capability_path: str, options: Any) -> None:
        if capability_path == self.HOVER_PROVIDER_KEY:
            self._increment_hover_count()

    def unregister_capability_async(self, capability_path: str) -> None:
        if capability_path == self.HOVER_PROVIDER_KEY:
            self._decrement_hover_count()

    def shutdown_async(self) -> None:
        listener = self.listener()
        if listener:
            listener.on_session_shutdown_async(self.session)

    def diagnostics_key(self, severity: int) -> str:
        return "lsp{}d{}".format(self.session.config.name, severity)

    def active_diagnostics_key(self) -> str:
        return "lsp{}d_".format(self.session.config.name)

    def present_diagnostics_async(self, flags: int) -> None:
        data_per_severity = self.session_buffer.data_per_severity
        for severity in reversed(range(1, len(DIAGNOSTIC_SEVERITY) + 1)):
            key = self.diagnostics_key(severity)
            data = data_per_severity.get(severity)
            if data is None:
                self.view.erase_regions(key)
            elif ((severity <= global_settings.show_diagnostics_severity_level) and
                    (data.icon or flags != (sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE))):
                self.view.add_regions(key, data.regions, data.scope, data.icon, flags)
            else:
                self.view.erase_regions(key)
        listener = self.listener()
        if listener:
            listener.update_active_diagnostic_async()

    def get_diagnostics_async(self) -> List[Diagnostic]:
        return self.session_buffer.diagnostics

    def update_active_diagnostic_async(self, r: Range) -> None:
        key = self.active_diagnostics_key()
        if global_settings.show_diagnostics_in_view_status:
            diags = []  # type: List[Diagnostic]
            for diag in self.session_buffer.diagnostics:
                if diag.range.intersects(r):
                    diags.append(diag)
            if diags:
                diags = sorted(diags, key=lambda d: d.severity)
                diag = diags[0]
                regions = [range_to_region(diag.range, self.view)]
                scope = DIAGNOSTIC_SEVERITY[diag.severity - 1][2]
                icon = ""
                flags = sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE
                annotations = [format_diagnostic_for_annotation(diag)]
                annotation_color = self.view.style_for_scope(scope)["foreground"]
                self.view.add_regions(key, regions, scope, icon, flags, annotations, annotation_color)
                return
        self.view.erase_regions(key)

    def on_text_changed_async(self, changes: Iterable[sublime.TextChange]) -> None:
        self.session_buffer.on_text_changed_async(changes)

    def on_revert_async(self) -> None:
        self.session_buffer.on_revert_async()

    def on_reload_async(self) -> None:
        self.session_buffer.on_reload_async()

    def purge_changes_async(self) -> None:
        self.session_buffer.purge_changes_async()

    def on_pre_save_async(self, old_file_name: str) -> None:
        self.session_buffer.on_pre_save_async(old_file_name)

    def on_post_save_async(self) -> None:
        self.session_buffer.on_post_save_async()

    def __str__(self) -> str:
        return '{}:{}'.format(self.session.config.name, self.view.id())
