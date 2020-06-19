from .core.edit import parse_text_edit
from .core.registry import LspTextCommand
from .core.registry import LSPViewEventListener
from .core.registry import sessions_for_view
from .core.registry import windows
from .core.sessions import Session
from .core.settings import settings
from .core.typing import Any, Callable, List, Optional
from .core.views import entire_content_region
from .core.views import text_document_formatting
from .core.views import text_document_range_formatting
from .core.views import will_save_wait_until
from .save_command import LspSaveCommand, SaveTask
import sublime
import sublime_plugin


def apply_response_to_view(response: Optional[List[dict]], view: sublime.View) -> None:
    edits = list(parse_text_edit(change) for change in response) if response else []
    view.run_command('lsp_apply_document_edit', {'changes': edits})


class WillSaveWaitTask(SaveTask):
    @classmethod
    def is_applicable(cls, view: sublime.View) -> bool:
        view_settings = view.settings()
        return bool(view.window()) and bool(view.file_name()) \
            and LSPViewEventListener.has_supported_syntax({'syntax': view_settings.get('syntax')})

    def __init__(self, view: sublime.View, on_complete: Callable[[], None]) -> None:
        super().__init__(view, on_complete)
        window = self._view.window()
        if not window:
            raise AttributeError('missing window')
        self._manager = windows.lookup(window)
        self._view_maybe_dirty = False

    def run(self) -> None:
        for session in sessions_for_view(self._view, 'textDocumentSync.willSaveWaitUntil'):
            self._purge_changes_if_needed()
            self._will_save_wait_until(session)
        else:
            self._on_complete()

    def _purge_changes_if_needed(self) -> None:
        # Supermassive hack that will go away later.
        listeners = sublime_plugin.view_event_listeners.get(self._view.id(), [])
        for listener in listeners:
            if listener.__class__.__name__ == 'DocumentSyncListener':
                listener.purge_changes()  # type: ignore
                break

    def _will_save_wait_until(self, session: Session) -> None:
        session.send_request(will_save_wait_until(self._view, reason=1),  # TextDocumentSaveReason.Manual
                             lambda response: self._apply_and_purge(response),
                             lambda error: self._apply_and_purge(None))

    def _apply_and_purge(self, response: Any) -> None:
        if response:
            apply_response_to_view(response, self._view)
            self._view_maybe_dirty = True
        self._on_complete()


class FormattingTask(SaveTask):
    @classmethod
    def is_applicable(cls, view: sublime.View) -> bool:
        view_settings = view.settings()
        view_format_on_save = view_settings.get('lsp_format_on_save', None)
        enabled = view_format_on_save if isinstance(view_format_on_save, bool) else settings.lsp_format_on_save
        return enabled and bool(view.window()) and bool(view.file_name()) \
            and LSPViewEventListener.has_supported_syntax({'syntax': view_settings.get('syntax')})

    def __init__(self, view: sublime.View, on_complete: Callable[[], None]) -> None:
        super().__init__(view, on_complete)
        window = self._view.window()
        if not window:
            raise AttributeError('missing window')
        self._manager = windows.lookup(window)

    def run(self) -> None:
        view_format_on_save = self._view.settings().get('lsp_format_on_save', None)
        enabled = view_format_on_save if isinstance(view_format_on_save, bool) else settings.lsp_format_on_save
        if enabled:
            self._purge_changes_if_needed()
            self._format_on_save()
        else:
            self._on_complete()

    def _purge_changes_if_needed(self) -> None:
        # Supermassive hack that will go away later.
        listeners = sublime_plugin.view_event_listeners.get(self._view.id(), [])
        for listener in listeners:
            if listener.__class__.__name__ == 'DocumentSyncListener':
                listener.purge_changes()  # type: ignore
                break

    def _format_on_save(self) -> None:
        session = next(sessions_for_view(self._view, 'documentFormattingProvider'))
        if session:
            session.send_request(text_document_formatting(self._view),
                                 lambda response: self._apply_and_purge(response),
                                 lambda error: self._apply_and_purge(None))
        else:
            self._on_complete()

    def _apply_and_purge(self, response: Any) -> None:
        if response:
            apply_response_to_view(response, self._view)
        self._on_complete()


LspSaveCommand.register_task(WillSaveWaitTask)
LspSaveCommand.register_task(FormattingTask)


class LspFormatDocumentCommand(LspTextCommand):

    capability = 'documentFormattingProvider'

    def is_enabled(self, event: Optional[dict] = None) -> bool:
        return super().is_enabled() or bool(self.session(LspFormatDocumentRangeCommand.capability))

    def run(self, edit: sublime.Edit, event: Optional[dict] = None) -> None:
        session = self.session(self.capability)
        if session:
            # Either use the documentFormattingProvider ...
            session.send_request(text_document_formatting(self.view), self.on_result)
        else:
            session = self.session(LspFormatDocumentRangeCommand.capability)
            if session:
                # ... or use the documentRangeFormattingProvider and format the entire range.
                req = text_document_range_formatting(self.view, entire_content_region(self.view))
                session.send_request(req, self.on_result)

    def on_result(self, params: Any) -> None:
        apply_response_to_view(params, self.view)


class LspFormatDocumentRangeCommand(LspTextCommand):

    capability = 'documentRangeFormattingProvider'

    def is_enabled(self, event: Optional[dict] = None) -> bool:
        if super().is_enabled(event):
            if len(self.view.sel()) == 1:
                region = self.view.sel()[0]
                if region.begin() != region.end():
                    return True
        return False

    def run(self, edit: sublime.Edit, event: Optional[dict] = None) -> None:
        session = self.session(self.capability)
        if session:
            session.send_request(
                text_document_range_formatting(self.view, self.view.sel()[0]),
                lambda response: apply_response_to_view(response, self.view))
