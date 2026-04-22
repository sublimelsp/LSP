import concurrent.futures
import threading
from typing import Any, Callable, TypeVar

import sublime


class _SetTimeoutAsyncExecutor(concurrent.futures.Executor):
    """
    An Executor that wraps sublime.set_timeout_async.
    """

    def __init__(self) -> None:
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

        sublime.set_timeout_async(run)
        return future

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        self._shuttingdown = True
        if wait:
            with self._cv:
                self._cv.wait_for(lambda: self._running == 0)


executor = _SetTimeoutAsyncExecutor()
