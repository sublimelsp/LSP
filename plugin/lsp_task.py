from __future__ import annotations

from .core.aio import run_coroutine
from .core.registry import LspTextCommand
from .core.settings import userprefs
from abc import ABC
from abc import abstractmethod
from typing import Any
from typing_extensions import override
import asyncio
import sublime


class LspTask(ABC):
    """
    Base class for tasks that run from `LspTextCommandWithTasks` command.

    Note: The whole task runs on the asyncio thread.
    """

    @classmethod
    @abstractmethod
    def is_applicable(cls, view: sublime.View) -> bool:
        pass

    def __init__(self, task_runner: LspTextCommand) -> None:
        self._text_command = task_runner
        self._status_key = type(self).__name__

    async def run(self) -> None:
        self._erase_view_status()

    def _erase_view_status(self) -> None:
        self._text_command.view.erase_status(self._status_key)

    def _purge_changes_async(self) -> None:
        if listener := self._text_command.get_listener():
            listener.purge_changes_async()


class LspTextCommandWithTasks(LspTextCommand, ABC):

    @property
    @abstractmethod
    def tasks(self) -> list[type[LspTask]]:
        """Returns tasks to run when command is run."""

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._tasks_runner: asyncio.Task | None = None

    def on_before_tasks(self) -> None:
        """Override this to execute code before the task handler starts."""

    async def on_tasks_completed(self, **kwargs: dict[str, Any]) -> None:
        """Override this to execute code when all tasks are completed."""

    @override
    def run(self, edit: sublime.Edit, **kwargs: dict[str, Any]) -> None:
        run_coroutine(self._run(**kwargs))

    async def _run(self, **kwargs: dict[str, Any]) -> None:
        if self._tasks_runner:
            if self._tasks_runner.cancel():
                try:
                    await self._tasks_runner
                except asyncio.CancelledError:
                    pass
                self._tasks_runner = None
        self.on_before_tasks()
        self._tasks_runner = asyncio.create_task(run_tasks(self, self.tasks))
        try:
            await asyncio.wait_for(self._tasks_runner, timeout=userprefs().on_save_task_timeout_ms / 1000)
        except asyncio.exceptions.TimeoutError:
            sublime.status_message('Running "on save" tasks took too long!')
        await self.on_tasks_completed(**kwargs)


async def run_tasks(text_command: LspTextCommandWithTasks, tasks: list[type[LspTask]]) -> None:
    for task in tasks:
        if task.is_applicable(text_command.view):
            await task(text_command).run()
