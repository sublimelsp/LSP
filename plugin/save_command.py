from __future__ import annotations
from .code_actions import CodeActionsOnFormatOnSaveTask
from .code_actions import CodeActionsOnSaveTask
from .formatting import FormatOnSaveTask
from .formatting import WillSaveWaitTask
from .lsp_task import LspTask
from .lsp_task import LspTextCommandWithTasks
from typing import Any
from typing_extensions import override
import sublime
import sublime_plugin


class LspSaveCommand(LspTextCommandWithTasks):
    """
    A command used as a substitute for native save command. Runs code actions and document
    formatting before triggering the native save command.
    """

    @property
    @override
    def tasks(self) -> list[type[LspTask]]:
        return [
            CodeActionsOnSaveTask,
            CodeActionsOnFormatOnSaveTask,
            FormatOnSaveTask,
            WillSaveWaitTask,
        ]

    @override
    def on_before_tasks(self) -> None:
        sublime.set_timeout_async(self._trigger_on_pre_save_async)

    @override
    def on_tasks_completed(self, **kwargs: dict[str, Any]) -> None:
        # Triggered from set_timeout to preserve original semantics of on_pre_save handling
        sublime.set_timeout(lambda: self.view.run_command('save', kwargs))

    def _trigger_on_pre_save_async(self) -> None:
        if listener := self.get_listener():
            listener.trigger_on_pre_save_async()


class LspSaveAllCommand(sublime_plugin.WindowCommand):

    @override
    def run(self, only_files: bool = False) -> None:
        done: set[int] = set()
        for view in self.window.views():
            buffer_id = view.buffer_id()
            if buffer_id in done:
                continue
            if not view.is_dirty():
                continue
            if only_files and view.file_name() is None:
                continue
            done.add(buffer_id)
            view.run_command("lsp_save", {'async': True})
