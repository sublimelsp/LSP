import sublime
from .core.configurations import is_supported_syntax
from .core.edit import parse_text_edit
from .core.registry import LspTextCommand, LSPViewEventListener, session_for_view, client_from_session
from .core.registry import sessions_for_view
from .core.sessions import Session
from .core.settings import client_configs
from .core.typing import Any, List, Optional
from .core.views import will_save_wait_until, text_document_formatting, text_document_range_formatting


def apply_response_to_view(response: Optional[List[dict]], view: sublime.View) -> None:
    edits = list(parse_text_edit(change) for change in response) if response else []
    view.run_command('lsp_apply_document_edit', {'changes': edits})


class FormatOnSaveListener(LSPViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)

    @classmethod
    def is_applicable(cls, view_settings: dict) -> bool:
        syntax = view_settings.get('syntax')
        if syntax:
            return is_supported_syntax(syntax, client_configs.all)
        return False

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
            self.manager.documents.purge_changes(self.view)
            self._view_maybe_dirty = False

    def _apply_and_purge(self, response: Any) -> None:
        if response:
            apply_response_to_view(response, self.view)
            self._view_maybe_dirty = True

    def _will_save_wait_until(self, session: Session) -> None:
        client = client_from_session(session)
        if client:
            client.execute_request(will_save_wait_until(self.view, reason=1),  # TextDocumentSaveReason.Manual
                                   lambda response: self._apply_and_purge(response))

    def _format_on_save(self) -> None:
        client = client_from_session(session_for_view(self.view, 'documentFormattingProvider'))
        if client:
            client.execute_request(text_document_formatting(self.view),
                                   lambda response: self._apply_and_purge(response))


class LspFormatDocumentCommand(LspTextCommand):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)

    def is_enabled(self, event: Optional[dict] = None) -> bool:
        return self.has_client_with_capability('documentFormattingProvider')

    def run(self, edit: sublime.Edit) -> None:
        client = self.client_with_capability('documentFormattingProvider')
        file_path = self.view.file_name()
        if client and file_path:
            client.send_request(
                text_document_formatting(self.view),
                lambda response: apply_response_to_view(response, self.view))


class LspFormatDocumentRangeCommand(LspTextCommand):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)

    def is_enabled(self, event: Optional[dict] = None) -> bool:
        if self.has_client_with_capability('documentRangeFormattingProvider'):
            if len(self.view.sel()) == 1:
                region = self.view.sel()[0]
                if region.begin() != region.end():
                    return True
        return False

    def run(self, edit: sublime.Edit) -> None:
        client = self.client_with_capability('documentRangeFormattingProvider')
        file_path = self.view.file_name()
        if client and file_path:
            region = self.view.sel()[0]
            client.send_request(
                text_document_range_formatting(self.view, region),
                lambda response: apply_response_to_view(response, self.view))
