import sublime
from .core.edit import parse_text_edit
from .core.registry import LspTextCommand, LSPViewEventListener, session_for_view
from .core.registry import sessions_for_view
from .core.sessions import Session
from .core.typing import Any, List, Optional
from .core.views import will_save_wait_until, text_document_formatting, text_document_range_formatting


def apply_response_to_view(response: Optional[List[dict]], view: sublime.View) -> None:
    edits = list(parse_text_edit(change) for change in response) if response else []
    view.run_command('lsp_apply_document_edit', {'changes': edits})


class FormatOnSaveListener(LSPViewEventListener):
    @classmethod
    def is_applicable(cls, view_settings: dict) -> bool:
        return cls.has_supported_syntax(view_settings)

    def on_pre_save(self) -> None:
        file_path = self.view.file_name()
        if not file_path:
            return

        self._view_maybe_dirty = True
        for session in sessions_for_view(self.view, 'textDocumentSync.willSaveWaitUntil'):
            self._purge_changes_if_needed()
            self._will_save_wait_until(session)

        if self.view.settings().get("lsp_format_on_save"):
            self._purge_changes_if_needed()
            self._format_on_save()

    def _purge_changes_if_needed(self) -> None:
        if self._view_maybe_dirty:
            self.purge_changes()
            self._view_maybe_dirty = False

    def _apply_and_purge(self, response: Any) -> None:
        if response:
            apply_response_to_view(response, self.view)
            self._view_maybe_dirty = True

    def _will_save_wait_until(self, session: Session) -> None:
        session.execute_request(will_save_wait_until(self.view, reason=1),  # TextDocumentSaveReason.Manual
                                lambda response: self._apply_and_purge(response))

    def _format_on_save(self) -> None:
        session = session_for_view(self.view, 'documentFormattingProvider')
        if session:
            session.execute_request(text_document_formatting(self.view),
                                    lambda response: self._apply_and_purge(response))


class LspFormatDocumentCommand(LspTextCommand):

    capability = 'documentFormattingProvider'

    def run(self, edit: sublime.Edit, event: Optional[dict] = None) -> None:
        session = self.session(self.capability)
        file_path = self.view.file_name()
        if session and file_path:
            session.send_request(
                text_document_formatting(self.view),
                lambda response: apply_response_to_view(response, self.view))


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
        file_path = self.view.file_name()
        if session and file_path:
            region = self.view.sel()[0]
            session.send_request(
                text_document_range_formatting(self.view, region),
                lambda response: apply_response_to_view(response, self.view))
