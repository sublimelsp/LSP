from __future__ import annotations

from ..protocol import TextDocumentSaveReason
from ..protocol import TextEdit
from .code_actions import CodeActionsOnFormatTask
from .core.aio import run_coroutine_threadsafe
from .core.collections import DottedDict
from .core.edit import apply_text_edits
from .core.protocol import Error
from .core.registry import LspTextCommand
from .core.registry import windows
from .core.settings import userprefs
from .core.views import entire_content_region
from .core.views import first_selection_region
from .core.views import has_single_nonempty_selection
from .core.views import text_document_formatting
from .core.views import text_document_range_formatting
from .core.views import text_document_ranges_formatting
from .core.views import will_save_wait_until
from .lsp_task import LspTask
from .lsp_task import LspTextCommandWithTasks
from functools import partial
from typing import Any
from typing import List
from typing import TYPE_CHECKING
from typing import Union
from typing_extensions import override
import sublime

if TYPE_CHECKING:
    from .core.sessions import Session

FormatResponse = Union[List[TextEdit], None]


def get_formatter(window: sublime.Window | None, base_scope: str) -> str | None:
    window_manager = windows.lookup(window)
    if not window_manager:
        return None
    project_data = window_manager.window.project_data()
    return DottedDict(project_data).get(f'settings.LSP.formatters.{base_scope}') if \
        isinstance(project_data, dict) else window_manager.formatters.get(base_scope)


async def format_document(text_command: LspTextCommand, formatter: str | None = None) -> FormatResponse:
    view = text_command.view
    if formatter:
        if session := text_command.session_by_name(formatter, LspFormatDocumentCommand.capability):
            return await session.request(text_document_formatting(view))
    if session := text_command.best_session(LspFormatDocumentCommand.capability):
        # Either use the documentFormattingProvider ...
        return await session.request(text_document_formatting(view))
    if session := text_command.best_session(LspFormatDocumentRangeCommand.capability):
        # ... or use the documentRangeFormattingProvider and format the entire range.
        return await session.request(text_document_range_formatting(view, entire_content_region(view)))
    return None


class WillSaveWaitTask(LspTask):
    @classmethod
    def is_applicable(cls, view: sublime.View) -> bool:
        return bool(view.file_name())

    def __init__(self, text_command: LspTextCommand) -> None:
        super().__init__(text_command)

    async def run(self) -> None:
        await super().run()
        for session in self._text_command.sessions('textDocumentSync.willSaveWaitUntil'):
            self._purge_changes_async()
            view = self._text_command.view
            try:
                if text_edits := await session.request(
                    will_save_wait_until(view, reason=TextDocumentSaveReason.Manual)
                ):
                    await apply_text_edits(self._text_command.view, text_edits, label="Format on Save")
            except Exception as ex:
                sublime.status_message(f"Failed to apply Will Save Task: {ex}")


class FormatOnSaveTask(LspTask):
    @classmethod
    @override
    def is_applicable(cls, view: sublime.View) -> bool:
        settings = view.settings()
        view_format_on_save = settings.get('lsp_format_on_save', None)
        enabled = view_format_on_save if isinstance(view_format_on_save, bool) else userprefs().lsp_format_on_save
        return enabled and bool(view.window()) and bool(view.file_name())

    @override
    async def run(self) -> None:
        await super().run()
        self._purge_changes_async()
        syntax = self._text_command.view.syntax()
        if not syntax:
            return
        base_scope = syntax.scope
        formatter = get_formatter(self._text_command.view.window(), base_scope)
        try:
            if text_edits := await format_document(self._text_command, formatter):
                await apply_text_edits(self._text_command.view, text_edits, label="Format On Save")
        except Exception as ex:
            sublime.status_message(f"Failed to apply Format On Save: {ex}")


class LspFormatDocumentCommand(LspTextCommandWithTasks):

    capability = 'documentFormattingProvider'

    label = 'Format File'

    @property
    @override
    def tasks(self) -> list[type[LspTask]]:
        return [CodeActionsOnFormatTask]

    @override
    def is_enabled(self, event: dict | None = None, select: bool = False) -> bool:
        if select:
            return len(list(self.sessions(self.capability))) > 1
        return super().is_enabled() or bool(self.best_session(LspFormatDocumentRangeCommand.capability))

    @override
    async def on_tasks_completed(self, *, select: bool = False, **kwargs: dict[str, Any]) -> None:
        session_names = [session.config.name for session in self.sessions(self.capability)]
        syntax = self.view.syntax()
        if not syntax:
            return
        base_scope = syntax.scope
        if select:
            self.select_formatter(base_scope, session_names)
            return
        if listener := self.get_listener():
            listener.purge_changes_async()
        if len(session_names) > 1:
            if formatter := get_formatter(self.view.window(), base_scope):
                if session := self.session_by_name(formatter, self.capability):
                    await self._apply_text_edits(
                        await session.request(text_document_formatting(self.view)), label=self.label
                    )
                    return
            self.select_formatter(base_scope, session_names)
        else:
            await self._apply_text_edits(await format_document(self), label=self.label)

    async def _apply_text_edits(self, text_edits: list[TextEdit] | None, label: str) -> None:
        try:
            if text_edits:
                await apply_text_edits(self.view, text_edits, label=label)
        except Exception as ex:
            sublime.status_message(f"Failed to {label}: {ex}")

    def select_formatter(self, base_scope: str, session_names: list[str]) -> None:
        if window := self.view.window():
            window.show_quick_panel(
                session_names,
                partial(self.on_select_formatter, base_scope, session_names),
                placeholder="Select Formatter"
            )

    def on_select_formatter(self, base_scope: str, session_names: list[str], index: int) -> None:
        if index == -1:
            return
        session_name = session_names[index]
        if window_manager := windows.lookup(self.view.window()):
            window = window_manager.window
            project_data = window.project_data()
            if isinstance(project_data, dict):
                project_settings = project_data.setdefault('settings', {})
                project_lsp_settings = project_settings.setdefault('LSP', {})
                project_formatter_settings = project_lsp_settings.setdefault('formatters', {})
                project_formatter_settings[base_scope] = session_name
                window_manager.suppress_sessions_restart_on_project_update = True
                window.set_project_data(project_data)
            else:  # Save temporarily for this window
                window_manager.formatters[base_scope] = session_name

            async def do_format() -> None:
                if session := self.session_by_name(session_name, self.capability):
                    if listener := self.get_listener():
                        listener.purge_changes_async()
                        await self._apply_text_edits(
                            await session.request(text_document_formatting(self.view)), label=self.label
                        )

            run_coroutine_threadsafe(do_format())


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
        run_coroutine_threadsafe(self._run())

    async def _run(self) -> None:
        if listener := self.get_listener():
            listener.purge_changes_async()
        session: Session | None = None
        text_edits: list[TextEdit] | None = None
        try:
            if has_single_nonempty_selection(self.view):
                session = self.best_session(self.capability)
                selection = first_selection_region(self.view)
                if session and selection is not None:
                    text_edits = await session.request(text_document_range_formatting(self.view, selection))
            elif self.view.has_non_empty_selection_region():
                if session := self.best_session('documentRangeFormattingProvider.rangesSupport'):
                    text_edits = await session.request(text_document_ranges_formatting(self.view))
            if text_edits is not None:
                await apply_text_edits(self.view, text_edits)
        except Error as error:
            sublime.status_message(f'Formatting error: {error}')


class LspFormatCommand(LspTextCommand):

    def is_enabled(self, event: dict | None = None, point: int | None = None) -> bool:
        if not super().is_enabled():
            return False
        return bool(self.best_session('documentFormattingProvider')) or \
            bool(self.best_session('documentRangeFormattingProvider'))

    def is_visible(self, event: dict | None = None, point: int | None = None) -> bool:
        return self.is_enabled(event, point)

    def description(self, **kwargs: Any) -> str:
        return "Format Selection" if self._range_formatting_available() else "Format File"

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
