from __future__ import annotations

from .core.registry import LspTextCommand
from .core.settings import userprefs
from abc import ABC
from abc import abstractmethod
from functools import partial
from typing import Any
from typing import Callable
from typing import final
from typing_extensions import override
import sublime


class LspTask(ABC):
    """
    Base class for tasks that run from `LspTextCommandWithTasks` command.

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


@final
class TasksRunner:
    def __init__(
        self, text_command: LspTextCommand, tasks: list[type[LspTask]], on_complete: Callable[[], None]
    ) -> None:
        self._text_command = text_command
        self._tasks = tasks
        self._on_tasks_completed = on_complete
        self._pending_tasks: list[LspTask] = []
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


class LspTextCommandWithTasks(LspTextCommand, ABC):

    @property
    @abstractmethod
    def tasks(self) -> list[type[LspTask]]:
        """Returns tasks to run when command is run."""

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._tasks_runner: TasksRunner | None = None

    def on_before_tasks(self) -> None:
        """Override this to execute code before the task handler starts."""

    def on_tasks_completed(self, **kwargs: dict[str, Any]) -> None:
        """Override this to execute code when all tasks are completed."""

    def _on_tasks_completed(self, **kwargs: dict[str, Any]) -> None:
        self._tasks_runner = None
        self.on_tasks_completed(**kwargs)

    @override
    def run(self, edit: sublime.Edit, **kwargs: dict[str, Any]) -> None:
        if self._tasks_runner:
            self._tasks_runner.cancel()
        self.on_before_tasks()
        self._tasks_runner = TasksRunner(self, self.tasks, partial(self._on_tasks_completed, **kwargs))
        self._tasks_runner.run()
