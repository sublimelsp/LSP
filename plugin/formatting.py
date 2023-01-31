from .core.edit import parse_text_edit
from .core.promise import Promise
from .core.protocol import Error
from .core.protocol import TextDocumentSaveReason
from .core.protocol import TextEdit
from .core.registry import LspTextCommand
from .core.sessions import Session
from .core.settings import userprefs
from .core.typing import Any, Callable, List, Optional, Iterator, Union
from .core.views import entire_content_region
from .core.views import first_selection_region
from .core.views import has_single_nonempty_selection
from .core.views import text_document_formatting
from .core.views import text_document_range_formatting
from .core.views import will_save_wait_until
from .save_command import LspSaveCommand, SaveTask
import sublime


FormatResponse = Union[List[TextEdit], None, Error]


def format_document(text_command: LspTextCommand) -> Promise[FormatResponse]:
    view = text_command.view
    session = text_command.best_session(LspFormatDocumentCommand.capability)
    if session:
        # Either use the documentFormattingProvider ...
        return session.send_request_task(text_document_formatting(view))
    session = text_command.best_session(LspFormatDocumentRangeCommand.capability)
    if session:
        # ... or use the documentRangeFormattingProvider and format the entire range.
        return session.send_request_task(text_document_range_formatting(view, entire_content_region(view)))
    return Promise.resolve(None)


def apply_text_edits_to_view(response: Optional[List[TextEdit]], view: sublime.View) -> None:
    edits = list(parse_text_edit(change) for change in response) if response else []
    view.run_command('lsp_apply_document_edit', {'changes': edits})


class WillSaveWaitTask(SaveTask):
    @classmethod
    def is_applicable(cls, view: sublime.View) -> bool:
        return bool(view.file_name())

    def __init__(self, task_runner: LspTextCommand, on_complete: Callable[[], None]) -> None:
        super().__init__(task_runner, on_complete)
        self._session_iterator = None  # type: Optional[Iterator[Session]]

    def run_async(self) -> None:
        super().run_async()
        self._session_iterator = self._task_runner.sessions('textDocumentSync.willSaveWaitUntil')
        self._handle_next_session_async()

    def _handle_next_session_async(self) -> None:
        session = next(self._session_iterator, None) if self._session_iterator else None
        if session:
            self._purge_changes_async()
            self._will_save_wait_until_async(session)
        else:
            self._on_complete()

    def _will_save_wait_until_async(self, session: Session) -> None:
        session.send_request_async(
            will_save_wait_until(self._task_runner.view, reason=TextDocumentSaveReason.Manual),
            self._on_response,
            lambda error: self._on_response(None))

    def _on_response(self, response: Any) -> None:
        if response and not self._cancelled:
            apply_text_edits_to_view(response, self._task_runner.view)
        sublime.set_timeout_async(self._handle_next_session_async)


class FormattingTask(SaveTask):
    @classmethod
    def is_applicable(cls, view: sublime.View) -> bool:
        settings = view.settings()
        view_format_on_save = settings.get('lsp_format_on_save', None)
        enabled = view_format_on_save if isinstance(view_format_on_save, bool) else userprefs().lsp_format_on_save
        return enabled and bool(view.window()) and bool(view.file_name())

    def run_async(self) -> None:
        super().run_async()
        self._purge_changes_async()
        format_document(self._task_runner).then(self._on_response)

    def _on_response(self, response: FormatResponse) -> None:
        if response and not isinstance(response, Error) and not self._cancelled:
            apply_text_edits_to_view(response, self._task_runner.view)
        sublime.set_timeout_async(self._on_complete)


LspSaveCommand.register_task(WillSaveWaitTask)
LspSaveCommand.register_task(FormattingTask)


class LspFormatDocumentCommand(LspTextCommand):

    capability = 'documentFormattingProvider'

    def is_enabled(self, event: Optional[dict] = None, point: Optional[int] = None) -> bool:
        return super().is_enabled() or bool(self.best_session(LspFormatDocumentRangeCommand.capability))

    def run(self, edit: sublime.Edit, event: Optional[dict] = None) -> None:
        format_document(self).then(self.on_result)

    def on_result(self, result: FormatResponse) -> None:
        if result and not isinstance(result, Error):
            apply_text_edits_to_view(result, self.view)


class LspFormatDocumentRangeCommand(LspTextCommand):

    capability = 'documentRangeFormattingProvider'

    def is_enabled(self, event: Optional[dict] = None, point: Optional[int] = None) -> bool:
        if super().is_enabled(event, point):
            return has_single_nonempty_selection(self.view)
        return False

    def run(self, edit: sublime.Edit, event: Optional[dict] = None) -> None:
        session = self.best_session(self.capability)
        selection = first_selection_region(self.view)
        if session and selection is not None:
            req = text_document_range_formatting(self.view, selection)
            session.send_request(req, lambda response: apply_text_edits_to_view(response, self.view))


class LspFormatCommand(LspTextCommand):

    def is_enabled(self, event: Optional[dict] = None, point: Optional[int] = None) -> bool:
        if not super().is_enabled():
            return False
        return bool(self.best_session('documentFormattingProvider')) or \
            bool(self.best_session('documentRangeFormattingProvider'))

    def is_visible(self, event: Optional[dict] = None, point: Optional[int] = None) -> bool:
        return self.is_enabled(event, point)

    def description(self, **kwargs) -> str:
        return "Format Selection" if self._range_formatting_available() else "Format File"

    def run(self, edit: sublime.Edit, event: Optional[dict] = None) -> None:
        command = 'lsp_format_document_range' if self._range_formatting_available() else 'lsp_format_document'
        self.view.run_command(command)

    def _range_formatting_available(self) -> bool:
        return has_single_nonempty_selection(self.view) and bool(self.best_session('documentRangeFormattingProvider'))
