from __future__ import annotations
from .core.collections import DottedDict
from .core.edit import apply_text_edits
from .core.promise import Promise
from .core.protocol import Error
from .core.protocol import TextDocumentSaveReason
from .core.protocol import TextEdit
from .core.registry import LspTextCommand
from .core.registry import windows
from .core.sessions import Session
from .core.settings import userprefs
from .core.views import entire_content_region
from .core.views import first_selection_region
from .core.views import has_single_nonempty_selection
from .core.views import text_document_formatting
from .core.views import text_document_range_formatting
from .core.views import text_document_ranges_formatting
from .core.views import will_save_wait_until
from .save_command import LspSaveCommand, SaveTask
from functools import partial
from typing import Callable, Iterator, List, Union
import sublime


FormatResponse = Union[List[TextEdit], None, Error]


def get_formatter(window: sublime.Window | None, base_scope: str) -> str | None:
    window_manager = windows.lookup(window)
    if not window_manager:
        return None
    project_data = window_manager.window.project_data()
    return DottedDict(project_data).get(f'settings.LSP.formatters.{base_scope}') if \
        isinstance(project_data, dict) else window_manager.formatters.get(base_scope)


def format_document(text_command: LspTextCommand, formatter: str | None = None) -> Promise[FormatResponse]:
    view = text_command.view
    if formatter:
        session = text_command.session_by_name(formatter, LspFormatDocumentCommand.capability)
        if session:
            return session.send_request_task(text_document_formatting(view))
    session = text_command.best_session(LspFormatDocumentCommand.capability)
    if session:
        # Either use the documentFormattingProvider ...
        return session.send_request_task(text_document_formatting(view))
    session = text_command.best_session(LspFormatDocumentRangeCommand.capability)
    if session:
        # ... or use the documentRangeFormattingProvider and format the entire range.
        return session.send_request_task(text_document_range_formatting(view, entire_content_region(view)))
    return Promise.resolve(None)


class WillSaveWaitTask(SaveTask):
    @classmethod
    def is_applicable(cls, view: sublime.View) -> bool:
        return bool(view.file_name())

    def __init__(self, task_runner: LspTextCommand, on_complete: Callable[[], None]) -> None:
        super().__init__(task_runner, on_complete)
        self._session_iterator: Iterator[Session] | None = None

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

    def _on_response(self, response: FormatResponse) -> None:
        if response and not isinstance(response, Error) and not self._cancelled:
            apply_text_edits(self._task_runner.view, response)
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
        syntax = self._task_runner.view.syntax()
        if not syntax:
            return
        base_scope = syntax.scope
        formatter = get_formatter(self._task_runner.view.window(), base_scope)
        format_document(self._task_runner, formatter).then(self._on_response)

    def _on_response(self, response: FormatResponse) -> None:
        if response and not isinstance(response, Error) and not self._cancelled:
            apply_text_edits(self._task_runner.view, response)
        sublime.set_timeout_async(self._on_complete)


LspSaveCommand.register_task(WillSaveWaitTask)
LspSaveCommand.register_task(FormattingTask)


class LspFormatDocumentCommand(LspTextCommand):

    capability = 'documentFormattingProvider'

    def is_enabled(self, event: dict | None = None, select: bool = False) -> bool:
        if select:
            return len(list(self.sessions(self.capability))) > 1
        return super().is_enabled() or bool(self.best_session(LspFormatDocumentRangeCommand.capability))

    def run(self, edit: sublime.Edit, event: dict | None = None, select: bool = False) -> None:
        session_names = [session.config.name for session in self.sessions(self.capability)]
        syntax = self.view.syntax()
        if not syntax:
            return
        base_scope = syntax.scope
        if select:
            self.select_formatter(base_scope, session_names)
        elif len(session_names) > 1:
            formatter = get_formatter(self.view.window(), base_scope)
            if formatter:
                session = self.session_by_name(formatter, self.capability)
                if session:
                    session.send_request_task(text_document_formatting(self.view)).then(self.on_result)
                    return
            self.select_formatter(base_scope, session_names)
        else:
            format_document(self).then(self.on_result)

    def on_result(self, result: FormatResponse) -> None:
        if result and not isinstance(result, Error):
            apply_text_edits(self.view, result)

    def select_formatter(self, base_scope: str, session_names: list[str]) -> None:
        window = self.view.window()
        if not window:
            return
        window.show_quick_panel(
            session_names, partial(self.on_select_formatter, base_scope, session_names), placeholder="Select Formatter")

    def on_select_formatter(self, base_scope: str, session_names: list[str], index: int) -> None:
        if index == -1:
            return
        session_name = session_names[index]
        window_manager = windows.lookup(self.view.window())
        if window_manager:
            window = window_manager.window
            project_data = window.project_data()
            if isinstance(project_data, dict):
                project_settings = project_data.setdefault('settings', dict())
                project_lsp_settings = project_settings.setdefault('LSP', dict())
                project_formatter_settings = project_lsp_settings.setdefault('formatters', dict())
                project_formatter_settings[base_scope] = session_name
                window_manager.suppress_sessions_restart_on_project_update = True
                window.set_project_data(project_data)
            else:  # Save temporarily for this window
                window_manager.formatters[base_scope] = session_name
        session = self.session_by_name(session_name, self.capability)
        if session:
            session.send_request_task(text_document_formatting(self.view)).then(self.on_result)


class LspFormatDocumentRangeCommand(LspTextCommand):

    capability = 'documentRangeFormattingProvider'

    def is_enabled(self, event: dict | None = None, point: int | None = None) -> bool:
        if not super().is_enabled(event, point):
            return False
        if has_single_nonempty_selection(self.view):
            return True
        if self.view.has_non_empty_selection_region() and \
                bool(self.best_session('documentRangeFormattingProvider.rangesSupport')):
            return True
        return False

    def run(self, edit: sublime.Edit, event: dict | None = None) -> None:
        if has_single_nonempty_selection(self.view):
            session = self.best_session(self.capability)
            selection = first_selection_region(self.view)
            if session and selection is not None:
                req = text_document_range_formatting(self.view, selection)
                session.send_request(req, lambda response: apply_text_edits(self.view, response))
        elif self.view.has_non_empty_selection_region():
            session = self.best_session('documentRangeFormattingProvider.rangesSupport')
            if session:
                req = text_document_ranges_formatting(self.view)
                session.send_request(req, lambda response: apply_text_edits(self.view, response))


class LspFormatCommand(LspTextCommand):

    def is_enabled(self, event: dict | None = None, point: int | None = None) -> bool:
        if not super().is_enabled():
            return False
        return bool(self.best_session('documentFormattingProvider')) or \
            bool(self.best_session('documentRangeFormattingProvider'))

    def is_visible(self, event: dict | None = None, point: int | None = None) -> bool:
        return self.is_enabled(event, point)

    def description(self, **kwargs) -> str:
        if self._range_formatting_available():
            if has_single_nonempty_selection(self.view):
                return "Format Selection"
            return "Format Selections"
        return "Format File"

    def run(self, edit: sublime.Edit, event: dict | None = None) -> None:
        command = 'lsp_format_document_range' if self._range_formatting_available() else 'lsp_format_document'
        self.view.run_command(command)

    def _range_formatting_available(self) -> bool:
        if has_single_nonempty_selection(self.view) and bool(self.best_session('documentRangeFormattingProvider')):
            return True
        if self.view.has_non_empty_selection_region() and \
                bool(self.best_session('documentRangeFormattingProvider.rangesSupport')):
            return True
        return False
