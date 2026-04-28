import concurrent.futures
import threading
from typing import Any, Callable, TypeVar

import sublime


class _Executor(concurrent.futures.Executor):
    """
    An Executor that wraps sublime.set_timeout(_async)

    Use in combination with an asyncio loop:

    ```python
    from .executors import executor_main, executor_async


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
executor_async = _Executor(sublime.set_timeout_async)
