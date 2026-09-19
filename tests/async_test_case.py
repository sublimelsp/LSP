from __future__ import annotations

from collections.abc import Generator
from typing import Any
from typing import Callable
from typing import Coroutine
from typing import Protocol
from typing_extensions import override
from unittesting import DeferrableTestCase
import asyncio
import inspect


class FutureLike(Protocol):
    def done(self) -> bool: ...
    def result(self) -> Any: ...
    def exception(self) -> BaseException | None: ...
    def cancelled(self) -> bool: ...
    def add_done_callback(self, fn: Callable[[FutureLike], Any]) -> None: ...


class AsyncTestCase(DeferrableTestCase):
    timeout_ms: int = 2000

    @classmethod
    def run_coroutine(cls, coro: Coroutine) -> FutureLike:
        """Override this method and run the given coroutine (using sublime_aio.run_coroutine for instance)."""
        raise NotImplementedError

    @classmethod
    def _runCoro(cls, coro: Coroutine[Any, Any, Any]) -> Generator:

        async def withTimeout() -> None:
            task = asyncio.create_task(coro)
            _, pending = await asyncio.wait({task}, timeout=cls.timeout_ms / 1000, return_when=asyncio.FIRST_COMPLETED)
            if task in pending:
                print("\n=== BEGIN: COROUTINE STACK BEFORE CANCELLATION ===")
                task.print_stack()
                print("=== END:   COROUTINE STACK BEFORE CANCELLATION ===")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                raise TimeoutError
            await task

        future = cls.run_coroutine(withTimeout())

        class Signal:
            def __init__(self) -> None:
                self.done = False
                self.exception: BaseException | None = None

            def check(self) -> bool:
                if self.exception:
                    raise self.exception
                return self.done

        signal = Signal()

        def onDone(future: FutureLike) -> None:
            if ex := future.exception():
                signal.exception = ex
            elif future.done():
                signal.done = True

        future.add_done_callback(onDone)
        yield {"condition": signal.check, "timeout": cls.timeout_ms}

    @classmethod
    async def asyncSetUpClass(cls) -> None:
        pass

    @classmethod
    async def asyncTearDownClass(cls) -> None:
        pass

    async def asyncDoCleanups(self) -> None:
        pass

    @override
    @classmethod
    def setUpClass(cls) -> Generator:
        yield from cls._runCoro(cls.asyncSetUpClass())

    @override
    @classmethod
    def tearDownClass(cls) -> Generator:
        yield from cls._runCoro(cls.asyncTearDownClass())

    @override
    def doCleanups(self) -> Generator:
        yield from self._runCoro(self.asyncDoCleanups())

    @override
    def _callSetUp(self) -> Generator | None:
        deferred = self.setUp()
        if isinstance(deferred, Generator):
            yield from deferred
        elif inspect.iscoroutine(deferred):
            yield from self._runCoro(deferred)

    @override
    def _callTestMethod(self, method: Callable[[], Coroutine | Generator | None]) -> Generator | None:
        deferred = method()
        if isinstance(deferred, Generator):
            yield from deferred
        elif inspect.iscoroutine(deferred):
            yield from self._runCoro(deferred)

    @override
    def _callTearDown(self) -> Generator | None:
        deferred = self.tearDown()
        if isinstance(deferred, Generator):
            yield from deferred
        elif inspect.iscoroutine(deferred):
            yield from self._runCoro(deferred)

    @override
    def _callCleanup(
        self, function: Callable[..., Coroutine | Generator | None], *args: Any, **kwargs: Any
    ) -> Generator | None:
        deferred = function(*args, **kwargs)
        if isinstance(deferred, Generator):
            yield from deferred
        elif inspect.iscoroutine(deferred):
            yield from self._runCoro(deferred)
