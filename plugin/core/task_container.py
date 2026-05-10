from .logging import exception_log, debug
from collections.abc import Coroutine
from typing import Any
import asyncio
import sublime_aio
import weakref


class TaskContainer:

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()

    def __del__(self) -> None:
        loop = asyncio.get_running_loop()
        if loop:
            tasks = set(self._tasks)
            for task in tasks:
                task.cancel()

    def create_task(self, coro: Coroutine, /, **kwargs: Any) -> asyncio.Task:
        """
        Spawn a new coroutine, to be run in the background. Not thread-safe. Must be invoked from the asyncio thread.

        First argument is the coroutine object, the named arguments are exactly the ones from asyncio.create_task.

        This method saves a strong reference to the spawned task, unlike asyncio.
        """
        debug(f"spawning new task with args: {coro=}, {kwargs=}")
        task = asyncio.create_task(coro, **kwargs)
        self._tasks.add(task)
        weakself = weakref.ref(self)

        def on_done(t: asyncio.Task) -> None:
            if this := weakself():
                this._tasks.discard(t)
            if t.cancelled():
                return
            if ex := task.exception():
                exception_log(f"Task {t.get_name()} finished with exception", ex)

        task.add_done_callback(on_done)
        return task

    def create_task_threadsafe(self, coro: Coroutine, /, **kwargs: Any) -> None:
        """
        Spawn a new coroutine, to be run in the background. Thread-safe.

        First argument is the coroutine object, the named arguments are exactly the ones from asyncio.create_task.
        """
        sublime_aio.call_soon_threadsafe(lambda: self.create_task(coro, **kwargs))
