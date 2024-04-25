from __future__ import annotations
from typing import Callable, Generic, Protocol, Tuple, TypeVar, Union
import functools
import threading

T = TypeVar('T')
S = TypeVar('S')
TExecutor = TypeVar('TExecutor')
T_contra = TypeVar('T_contra', contravariant=True)
TResult = TypeVar('TResult')


class ResolveFunc(Protocol[T_contra]):
    def __call__(self, resolve_value: T_contra) -> None:
        ...


FullfillFunc = Callable[[T], Union[TResult, 'Promise[TResult]']]
ExecutorFunc = Callable[[ResolveFunc[T]], None]
PackagedTask = Tuple['Promise[T]', ResolveFunc[T]]


class Promise(Generic[T]):
    """A simple implementation of the Promise specification.

    See: https://promisesaplus.com

    Promise is in essence a syntactic sugar for callbacks. Simplifies passing
    values from functions that might do work in asynchronous manner.

    Example usage:

      * Passing return value of one function to another:

        def do_work_async(resolve):
            # "resolve" is a function that, when called with a value, resolves
            # the promise with provided value and passes the value to the next
            # chained promise.
            resolve(111)  # Can be invoked asynchronously.

        def process_value(value):
            assert value === 111

        Promise(do_work_async).then(process_value)

      * Returning Promise from chained promise:

        def do_work_async_1(resolve):
            # Compute value asynchronously.
            resolve(111)

        def do_work_async_2(resolve):
            # Compute value asynchronously.
            resolve(222)

        def do_more_work_async(value):
            # Do more work with the value asynchronously. For the sake of this
            # example, we don't use 'value' for anything.
            assert value === 111
            return Promise(do_work_async_2)

        def process_value(value):
            assert value === 222

        Promise(do_work_async_1).then(do_more_work_async).then(process_value)
    """

    @staticmethod
    def resolve(resolve_value: S) -> Promise[S]:
        """Immediately resolves a Promise.

        Convenience function for creating a Promise that gets immediately
        resolved with the specified value.

        Arguments:
            resolve_value: The value to resolve the promise with.
        """
        def executor_func(resolve_fn: ResolveFunc[S]) -> None:
            resolve_fn(resolve_value)

        return Promise(executor_func)

    @staticmethod
    def packaged_task() -> PackagedTask[S]:

        class Executor(Generic[TExecutor]):

            __slots__ = ("resolver",)

            def __init__(self) -> None:
                self.resolver: ResolveFunc[TExecutor] | None = None

            def __call__(self, resolver: ResolveFunc[TExecutor]) -> None:
                self.resolver = resolver

        executor: Executor[S] = Executor()
        promise = Promise(executor)
        assert callable(executor.resolver)
        return promise, executor.resolver

    # Could also support passing plain S.
    @staticmethod
    def all(promises: list[Promise[S]]) -> Promise[list[S]]:
        """
        Takes a list of promises and returns a Promise that gets resolved when all promises
        gets resolved.

        :param      promises: The list of promises

        :returns:   A promise that gets resolved when all passed promises gets resolved.
                    Gets passed a list with all resolved values.
        """
        def executor(resolve: ResolveFunc[list[S]]) -> None:
            was_resolved = False

            def recheck_resolve_status(_: S) -> None:
                nonlocal was_resolved
                # We're being called from a Promise that is holding a lock so don't try to use
                # any methods that would try to acquire it.
                if not was_resolved and all(p.resolved for p in promises):
                    was_resolved = True
                    values = [p.value for p in promises]
                    resolve(values)

            for p in promises:
                assert isinstance(p, Promise)
                p.then(recheck_resolve_status)

        if promises:
            return Promise(executor)
        return Promise.resolve([])

    def __init__(self, executor_func: ExecutorFunc[T]) -> None:
        """Initialize Promise object.

        Arguments:
            executor_func: A function that is executed immediately by this Promise.
            It gets passed a "resolve" function. The "resolve" function, when
            called, resolves the Promise with the value passed to it.
        """
        self.resolved = False
        self.mutex = threading.Lock()
        self.callbacks: list[ResolveFunc[T]] = []
        executor_func(lambda resolve_value=None: self._do_resolve(resolve_value))

    def __repr__(self) -> str:
        if self.resolved:
            return f'Promise({self.value})'
        return 'Promise(<pending>)'

    def then(self, onfullfilled: FullfillFunc[T, TResult]) -> Promise[TResult]:
        """Create a new promise and chain it with this promise.

        When this promise gets resolved, the callback will be called with the
        value that this promise resolved with.

        Returns a new promise that can be used to do further chaining.

        Arguments:
            onfullfilled: The callback to call when this promise gets resolved.
        """
        def callback_wrapper(resolve_fn: ResolveFunc[TResult], resolve_value: T) -> None:
            """A wrapper called when this promise resolves.

            Arguments:
                resolve_fn: A resolve function of newly created promise.
                resolve_value: The value with which this promise resolved.
            """
            result = onfullfilled(resolve_value)
            # If returned value is a promise then this promise needs to be
            # resolved with the value of returned promise.
            if isinstance(result, Promise):
                result.then(lambda value: resolve_fn(value))
            else:
                resolve_fn(result)

        def sync_wrapper(resolve_fn: ResolveFunc[TResult]) -> None:
            """Call resolve_fn immediately with the resolved value.

            A wrapper function that will immediately resolve resolve_fn with the
            resolved value of this promise.
            """
            callback_wrapper(resolve_fn, self._get_value())

        def async_wrapper(resolve_fn: ResolveFunc[TResult]) -> None:
            """Queue resolve_fn to be called after this promise resolves later.

            A wrapper function that will resolve received resolve_fn when this promise
            resolves later.
            """
            self._add_callback(functools.partial(callback_wrapper, resolve_fn))

        if self._is_resolved():
            return Promise(sync_wrapper)
        return Promise(async_wrapper)

    def _do_resolve(self, new_value: T) -> None:
        # No need to block as we can't change from resolved to unresolved.
        if self.resolved:
            raise RuntimeError("cannot set the value of an already resolved promise")
        with self.mutex:
            self.resolved = True
            self.value = new_value
            for callback in self.callbacks:
                callback(new_value)

    def _add_callback(self, callback: ResolveFunc[T]) -> None:
        with self.mutex:
            self.callbacks.append(callback)

    def _is_resolved(self) -> bool:
        with self.mutex:
            return self.resolved

    def _get_value(self) -> T:
        with self.mutex:
            return self.value
