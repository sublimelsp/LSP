from __future__ import annotations
from .core.registry import LspTextCommand
from .core.settings import userprefs
from abc import ABCMeta, abstractmethod
from functools import partial
from typing import Any, Callable
import sublime
import sublime_plugin


class SaveTask(metaclass=ABCMeta):
    """
    Base class for tasks that run on save.

    Note: The whole task runs on the async thread.
    """

    @classmethod
    @abstractmethod
    def is_applicable(cls, view: sublime.View) -> bool:
        pass

    def __init__(self, task_runner: LspTextCommand, on_done: Callable[[], None]):
        self._task_runner = task_runner
        self._on_done = on_done
        self._completed = False
        self._cancelled = False
        self._status_key = type(self).__name__

    def run_async(self) -> None:
        self._erase_view_status()
        sublime.set_timeout_async(self._on_timeout, userprefs().on_save_task_timeout_ms)

    def _on_timeout(self) -> None:
        if not self._completed and not self._cancelled:
            self._set_view_status(f'LSP: Timeout processing {self.__class__.__name__}')
            self._cancelled = True
            self._on_done()

    def cancel(self) -> None:
        self._cancelled = True

    def _set_view_status(self, text: str) -> None:
        self._task_runner.view.set_status(self._status_key, text)
        sublime.set_timeout_async(self._erase_view_status, 5000)

    def _erase_view_status(self) -> None:
        self._task_runner.view.erase_status(self._status_key)

    def _on_complete(self) -> None:
        assert not self._completed
        self._completed = True
        if not self._cancelled:
            self._on_done()

    def _purge_changes_async(self) -> None:
        if listener := self._task_runner.get_listener():
            listener.purge_changes_async()


class SaveTasksRunner:
    def __init__(
        self, text_command: LspTextCommand, tasks: list[type[SaveTask]], on_complete: Callable[[], None]
    ) -> None:
        self._text_command = text_command
        self._tasks = tasks
        self._on_tasks_completed = on_complete
        self._pending_tasks: list[SaveTask] = []
        self._canceled = False

    def run(self) -> None:
        for task in self._tasks:
            if task.is_applicable(self._text_command.view):
                self._pending_tasks.append(task(self._text_command, self._on_task_completed_async))
        self._process_next_task()

    def cancel(self) -> None:
        for task in self._pending_tasks:
            task.cancel()
        self._pending_tasks = []
        self._canceled = True

    def _process_next_task(self) -> None:
        if self._pending_tasks:
            # Even though we might be on an async thread already, we want to give ST a chance to notify us about
            # potential document changes.
            sublime.set_timeout_async(self._run_next_task_async)
        else:
            self._on_tasks_completed()

    def _run_next_task_async(self) -> None:
        if self._canceled:
            return
        current_task = self._pending_tasks[0]
        current_task.run_async()

    def _on_task_completed_async(self) -> None:
        self._pending_tasks.pop(0)
        self._process_next_task()


class LspTextCommandWithTasks(LspTextCommand):
    _tasks: list[type[SaveTask]] = []

    @classmethod
    def register_task(cls, task: type[SaveTask]) -> None:
        assert task not in cls._tasks
        cls._tasks.append(task)

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._save_tasks_runner: SaveTasksRunner | None = None

    def on_before_tasks(self) -> None:
        """Override this to execute code before the task handler starts."""

    def on_tasks_completed(self, **kwargs: dict[str, Any]) -> None:
        """Override this to execute code when all tasks are completed."""

    def _on_tasks_completed(self, **kwargs: dict[str, Any]) -> None:
        self._save_tasks_runner = None
        self.on_tasks_completed(**kwargs)

    def run(self, edit: sublime.Edit, **kwargs: dict[str, Any]) -> None:
        if self._save_tasks_runner:
            self._save_tasks_runner.cancel()
        self.on_before_tasks()
        self._save_tasks_runner = SaveTasksRunner(self, self._tasks, partial(self._on_tasks_completed, **kwargs))
        self._save_tasks_runner.run()


class LspSaveCommand(LspTextCommandWithTasks):
    """
    A command used as a substitute for native save command. Runs code actions and document
    formatting before triggering the native save command.
    """
    def on_before_tasks(self) -> None:
        sublime.set_timeout_async(self._trigger_on_pre_save_async)

    def _trigger_on_pre_save_async(self) -> None:
        if listener := self.get_listener():
            listener.trigger_on_pre_save_async()

    def on_tasks_completed(self, **kwargs: dict[str, Any]) -> None:
        # Triggered from set_timeout to preserve original semantics of on_pre_save handling
        sublime.set_timeout(lambda: self.view.run_command('save', kwargs))


class LspSaveAllCommand(sublime_plugin.WindowCommand):
    def run(self, only_files: bool = False) -> None:
        done = set()
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
