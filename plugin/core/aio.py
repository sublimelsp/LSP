"""Functionality wrapping asyncio, sublime_aio, and interaction nuances with Sublime Text."""

from __future__ import annotations

from .logging import debug
from .logging import exception_log
from typing import Any
from typing import AsyncIterator
from typing import Callable
from typing import Coroutine
from typing import Protocol
from typing import TYPE_CHECKING
from typing import TypeVar
import asyncio
import concurrent.futures
import contextlib
import sublime
import sublime_aio
import sys
import threading

if TYPE_CHECKING:
    from contextvars import Context


class SupportsAclose(Protocol):
    async def aclose(self) -> None: ...


T = TypeVar("T")
S = TypeVar("S", bound="SupportsAclose")


# `async with aclosing(stream(...))`. This function in the contextlib module is available since python 3.10, but we also
# need to support python 3.8.
# See: https://docs.python.org/3/library/contextlib.html#contextlib.aclosing
if sys.version_info >= (3, 10, 0):
    aclosing = contextlib.aclosing
else:

    @contextlib.asynccontextmanager
    async def aclosing(thing: S) -> AsyncIterator[S]:
        try:
            yield thing
        finally:
            await thing.aclose()


_futures: set[concurrent.futures.Future] = set()


def run_coroutine_threadsafe(coroutine: Coroutine[object, object, T]) -> concurrent.futures.Future[T]:
    """
    Start the execution of a coroutine in the asyncio thread, from any thread.

    When you are certain you are already in the asyncio thread, then there are better ways to start a coroutine from a
    "blocking" ("non-async") function. One way is to use
    [asyncio.create_task](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.create_task). However,
    asyncio.create_task has the caveat that the returned [Task](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task)
    object must be kept alive somewhere. If you don't care about keeping tasks associated to coroutines alive, then
    inherit from the `TaskContainer` mixin class and use its `create_task` method.

    A big caveat: coroutines started this way do not print their exceptions when an exception occurs in the coroutine.
    To handle this, call `.add_done_callback` on the returned `Future` object.
    """
    future: concurrent.futures.Future[T] = sublime_aio.run_coroutine(coroutine)  # type: ignore

    def on_done(fut: concurrent.futures.Future[T]) -> None:
        _futures.discard(fut)
        if not fut.cancelled() and (ex := fut.exception()):
            exception_log("coroutine finished with exception", ex)

    future.add_done_callback(on_done)
    _futures.add(future)
    return future


def call_soon_threadsafe(f: Callable[..., Any], *args: Any, context: Context | None = None) -> asyncio.Handle:
    """Invoke a function in the asyncio thread, from any thread."""
    return sublime_aio.call_soon_threadsafe(f, *args, context=context)


class _Executor(concurrent.futures.Executor):
    """
    An Executor that wraps sublime.set_timeout(_async).

    Use in combination with an asyncio loop:

    ```python
    from LSP.core.aio import executor_main, executor_async


    def some_blocking_function_that_interacts_with_gui() -> int:
        window = sublime.current_window()
        return 42


    async def foo() -> int:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(executor_main, some_blocking_function_that_interacts_with_gui)
        return result


    def some_cpu_heavy_function() -> int:
        time.sleep(1)
        return 42


    async def bar() -> int:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(executor_async, some_cpu_heavy_function)
        return result
    ```
    """

    def __init__(self, dispatch_func: Callable[[Callable[..., Any]], Any]) -> None:
        self._dispatch_func = dispatch_func
        self._running = 0
        self._shuttingdown = False
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> concurrent.futures.Future:
        if self._shuttingdown:
            raise RuntimeError("Executor is shutting down")
        future: concurrent.futures.Future = concurrent.futures.Future()
        with self._cv:
            self._running += 1

        def run() -> None:
            try:
                future.set_result(fn(*args, **kwargs))
            except BaseException as ex:
                future.set_exception(ex)
            with self._cv:
                self._running -= 1
                if self._running == 0:
                    self._cv.notify()

        self._dispatch_func(run)
        return future

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        self._shuttingdown = True
        if wait:
            with self._cv:
                self._cv.wait_for(lambda: self._running == 0)


executor_main = _Executor(sublime.set_timeout)
"""Executor instance that runs functions on the Sublime Text main (GUI) thread."""

executor_async = _Executor(sublime.set_timeout_async)
"""Executor instance that runs functions on the Sublime Text "async" thread."""


async def next_frame() -> None:
    """Wait until (at least one) UI frame has passed."""

    def noop() -> None:
        pass

    await asyncio.get_running_loop().run_in_executor(executor_main, noop)


async def gather_and_flatten_exceptions(*coros: Coroutine[Any, Any, list[Exception]]) -> list[Exception]:
    """
    Takes a list of coroutines, runs them concurrently using asyncio.gather, collects all exceptions, and returns a
    flattened list of Exceptions that occurred for each coroutine. BaseExceptions are filtered out.
    """
    exceptions: list[Exception] = []
    items: list[BaseException | list[Exception]] = await asyncio.gather(*coros, return_exceptions=True)
    for item in items:
        # Only keep exceptions derived from Exception. Exceptions derived from BaseException, but not derived from
        # Exception are things like asyncio.CancelledError or SystemExit and should be ignored.
        if isinstance(item, Exception):
            exceptions.append(item)
        elif isinstance(item, list):
            exceptions.extend(item)
    return exceptions


class TaskContainer:
    """
    A [mixin class](https://en.wikipedia.org/wiki/Mixin) for adding "fire-and-forget" functionality to a class for
    starting coroutines.

    Note: don't forget to call `super().__init__()` when using this class.

    Ensure the `cancel_all_tasks` async function is ran before this class is destroyed.
    """

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()

    def __del__(self) -> None:
        if self._tasks:
            debug("WARNING: TaskContainer is destroyed but there are still tasks running!")

    async def cancel_all_tasks(self) -> list[Exception]:
        return [x for x in await asyncio.gather(*self._tasks, return_exceptions=True) if isinstance(x, Exception)]

    def create_task(self, coro: Coroutine[object, object, object], /, **kwargs: Any) -> asyncio.Task:
        """
        Spawn a new coroutine, to be run in the background. Not thread-safe. Must be invoked from the asyncio thread.

        First argument is the coroutine object, the named arguments are exactly the ones from asyncio.create_task.

        This method saves a strong reference to the spawned task, unlike asyncio.
        Moreover, this method will print any exception that occured during the exception of the coroutine, if any.
        """
        task = asyncio.create_task(coro, **kwargs)
        tasks = self._tasks
        tasks.add(task)

        def on_done(t: asyncio.Task) -> None:
            tasks.discard(t)
            if t.cancelled():
                return
            if ex := t.exception():
                exception_log(f"Task {t.get_name()} finished with exception", ex)

        task.add_done_callback(on_done)
        return task

    def create_task_threadsafe(self, coro: Coroutine[object, object, object], /, **kwargs: Any) -> None:
        """
        Spawn a new coroutine, to be run in the background. Thread-safe.

        First argument is the coroutine object, the named arguments are exactly the ones from asyncio.create_task.

        This method saves a strong reference to the spawned task, unlike asyncio.
        Moreover, this method will print any exception that occured during the exception of the coroutine, if any.
        """
        call_soon_threadsafe(lambda: self.create_task(coro, **kwargs))
