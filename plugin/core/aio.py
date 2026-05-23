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
import contextlib
import sublime
import sublime_aio
import sys

if TYPE_CHECKING:
    from contextvars import Context
    import concurrent.futures


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


def run_coroutine(coroutine: Coroutine[object, object, T]) -> concurrent.futures.Future[T]:
    """
    Start the execution of a coroutine in the asyncio thread, from any thread.

    When you are certain you are already in the asyncio thread, then use one of:

    * [asyncio.create_task](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.create_task). The
    caveat for asyncio.create_task is that the returned [Task](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task)
    object must be kept alive manually. The event loop only keeps a weak reference to the Task object.
    * `TaskContainer.create_task`: restricts the lifetime of the task to the lifetime of the `TaskContainer`. Unlike
      `asyncio.create_task`, keeps a (strong) reference to the Task object.
    """
    future = sublime_aio.run_coroutine(coroutine)

    def on_done(fut: concurrent.futures.Future[T]) -> None:
        _futures.discard(fut)
        if not fut.cancelled() and (ex := fut.exception()):
            exception_log("coroutine finished with exception", ex)

    future.add_done_callback(on_done)
    _futures.add(future)
    return future


def run_in_asyncio_thread(f: Callable[..., Any], *args: Any, context: Context | None = None) -> asyncio.Handle:
    """Invoke a function in the asyncio thread, from any thread."""
    return sublime_aio.call_soon_threadsafe(f, *args, context=context)


def _run_in_st_thread(
    dispatch_func: Callable[[Callable[[], None]], None], f: Callable[..., T], *args: Any, **kwargs: Any
) -> asyncio.Future[T]:
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def wrap() -> None:
        try:
            loop.call_soon_threadsafe(future.set_result, f(*args, **kwargs))
        except BaseException as ex:
            loop.call_soon_threadsafe(future.set_exception, ex)

    dispatch_func(wrap)
    return future


def run_in_main_thread(f: Callable[..., T], *args: Any, **kwargs: Any) -> asyncio.Future[T]:
    """
    Run a function in Sublime's main (UI) thread.

    Must be called from the asyncio thread. You must await the returned future.
    """
    return _run_in_st_thread(sublime.set_timeout, f, *args, **kwargs)


def run_in_async_thread(f: Callable[..., T], *args: Any, **kwargs: Any) -> asyncio.Future[T]:
    """
    Run a function in Sublime's async, or worker, thread.

    Must be called from the asyncio thread. You must await the returned future.
    """
    return _run_in_st_thread(sublime.set_timeout_async, f, *args, **kwargs)


def next_frame() -> asyncio.Future[None]:
    """Wait until (at least one) UI frame has passed."""

    def noop() -> None:
        pass

    return run_in_main_thread(noop)


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
        """Cancel all running tasks."""
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        return [x for x in await asyncio.gather(*self._tasks, return_exceptions=True) if isinstance(x, Exception)]

    def create_task(self, coro: Coroutine[object, object, object], name: str | None = None) -> asyncio.Task:
        """
        Spawn a new coroutine, to be run in the background. Not thread-safe. Must be invoked from the asyncio thread.

        This method saves a strong reference to the spawned task, unlike asyncio.
        Moreover, this method will print any exception that occured during the exception of the coroutine, if any.

        :param coro: The coroutine object to schedule.
        :param name: An optional name to give to the task. If no name has been explicitly assigned to the Task, the
        default asyncio Task implementation generates a default name during instantiation.
        :return: the newly created [Task](https://docs.python.org/3/library/asyncio-task.html#task-object) object.

        """
        task = asyncio.create_task(coro, name=name)
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

    def create_task_threadsafe(self, coro: Coroutine[object, object, object], name: str | None = None) -> None:
        """
        Spawn a new coroutine, to be run in the background. Thread-safe.

        The parameters and behavior of this method are exactly the same as :py:meth`create_task`.
        """
        run_in_asyncio_thread(lambda: self.create_task(coro, name=name))
