from __future__ import annotations

from .core.aio import PortableTimeoutError
from .core.aio import run_coroutine
from .core.registry import LspTextCommand
from .core.settings import userprefs
from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import final
from typing_extensions import override
import asyncio
import functools
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

    @final
    @property
    def status_key(self) -> str:
        return self._status_key

    async def run(self) -> None:
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

    def _set_view_status(self, status_key: str, text: str) -> None:
        self.view.set_status(status_key, text)
        sublime.set_timeout_async(functools.partial(self._erase_view_status, status_key), 5000)

    def _erase_view_status(self, status_key: str) -> None:
        self.view.erase_status(status_key)

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
        cancelled = False
        self._tasks_runner = asyncio.create_task(self._run_tasks())
        try:
            await self._tasks_runner
        except Exception:
            sublime.status_message("Error running save tasks. See the Console for more information.")
            raise
        except asyncio.CancelledError:
            cancelled = True
            raise
        finally:
            if not cancelled:
                await self.on_tasks_completed(**kwargs)

    async def _run_tasks(self) -> None:
        for task_type in self.tasks:
            if task_type.is_applicable(self.view):
                task = task_type(self)
                try:
                    await asyncio.wait_for(task_type(self).run(), timeout=userprefs().on_save_task_timeout_ms / 1000)
                except PortableTimeoutError:
                    self._set_view_status(task.status_key, f'Timeout processing {task.__name__}')
