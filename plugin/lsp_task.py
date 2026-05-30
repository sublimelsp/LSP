from __future__ import annotations

from .core.aio import run_coroutine
from .core.logging import exception_log
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

    async def _purge_changes(self) -> None:
        if listener := self._text_command.get_listener():
            await listener.purge_changes()


class LspTextCommandWithTasks(LspTextCommand, ABC):

    @property
    @abstractmethod
    def tasks(self) -> list[type[LspTask]]:
        """Returns tasks to run when command is run."""

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self._tasks_runner: asyncio.Task | None = None

    async def on_before_tasks(self) -> None:
        """Override this to execute code before the task handler starts."""

    async def on_tasks_completed(self, **kwargs: dict[str, Any]) -> None:
        """Override this to execute code when all tasks are completed."""

    @override
    def run(self, edit: sublime.Edit, **kwargs: dict[str, Any]) -> None:
        run_coroutine(self._run(**kwargs))

    async def _run(self, **kwargs: dict[str, Any]) -> None:
        if self._tasks_runner:
            # Request to cancel the task.
            if self._tasks_runner.cancel():
                try:
                    # Wait for the task to actually finish.
                    await self._tasks_runner
                except asyncio.CancelledError:
                    # It's going to throw this exception so catch it.
                    pass
                self._tasks_runner = None
        await self.on_before_tasks()
        self._tasks_runner = asyncio.create_task(self._run_tasks())
        try:
            await asyncio.wait_for(self._tasks_runner, timeout=userprefs().on_save_task_timeout_ms / 1000)
        except asyncio.exceptions.TimeoutError:
            sublime.status_message('Running "on save" tasks took too long!')
        except Exception as ex:
            sublime.status_message("Error running save tasks. See the Console for more information.")
            exception_log("Error running save tasks", ex)
        finally:
            await self.on_tasks_completed(**kwargs)

    async def _run_tasks(self) -> None:
        for task in self.tasks:
            if task.is_applicable(self.view):
                await task(self).run()
