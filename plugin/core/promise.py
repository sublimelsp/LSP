from .typing import Any, Callable, List
import functools
import threading

ResolveFunc = Callable[..., None]  # Optional argument not supported in Callable so using "..."
FullfillFunc = Callable[[ResolveFunc], None]
ThenFunc = Callable[[Any], Any]


class Promise:
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

    @classmethod
    def resolve(cls, resolve_value: Any = None) -> 'Promise':
        """Immediately resolves a Promise.

        Convenience function for creating a Promise that gets immediately
        resolved with the specified value.

        Arguments:
            resolve_value: The value to resolve the promise with.
        """
        def fullfill_func(resolve_fn: ResolveFunc) -> None:
            resolve_fn(resolve_value)

        return cls(fullfill_func)

    @classmethod
    def all(cls, promises: List['Promise']) -> 'Promise':
        """
        Takes a list of promises and returns a Promise that gets resolved when all promises
        gets resolved.

        :param      promises: The list of promises

        :returns:   A promise that gets resolved when all passed promises gets resolved.
                    Gets passed a list with all resolved values.
        """
        def handler(resolve: ResolveFunc) -> None:
            was_resolved = False

            def recheck_resolve_status(_: Any) -> None:
                nonlocal was_resolved
                # We're being called from a Promise that is holding a lock so don't try to use
                # any methods that would try to acquire it.
                if not was_resolved and all(p.resolved for p in promises):
                    was_resolved = True
                    resolve([p.value for p in promises])

            for p in promises:
                if not isinstance(p, Promise):
                    raise Exception('Value is not a Promise')
                p.then(recheck_resolve_status)

        if promises:
            return Promise(handler)
        return Promise.resolve()

    def __init__(self, fullfill_func: FullfillFunc) -> None:
        """Initialize Promise object.

        Arguments:
            fullfill_func: A function that is executed immediately by this Promise.
            It gets passed a "resolve" function. The "resolve" function, when
            called, resolves the Promise with the value passed to it.
        """
        self.value = None  # type: Any
        self.resolved = False
        self.mutex = threading.Lock()
        self.callbacks = []  # type: List[ResolveFunc]
        fullfill_func(lambda value=None: self._do_resolve(value))

    def __repr__(self) -> str:
        if self.resolved:
            return 'Promise({})'.format(self.value)
        return 'Promise(<pending>)'

    def then(self, callback: ThenFunc) -> 'Promise':
        """Create a new promise and chain it with this promise.

        When this promise gets resolved, the callback will be called with the
        value that this promise resolved with.

        Returns a new promise that can be used to do further chaining.

        Arguments:
            callback: The callback to call when this promise gets resolved.
        """
        def callback_wrapper(resolve_fn: ThenFunc, resolve_value: Any) -> None:
            """A wrapper called when this promise resolves.

            Arguments:
                resolve_fn: A resolve function of newly created promise.
                resolve_value: The value with which this promise resolved.
            """
            result = callback(resolve_value)
            # If returned value is a promise then this promise needs to be
            # resolved with the value of returned promise.
            if isinstance(result, Promise):
                result.then(resolve_fn)
            else:
                resolve_fn(result)

        def sync_wrapper(resolve_fn: ThenFunc) -> None:
            """Call resolve_fn immediately with the resolved value.

            A wrapper function that will immediately resolve resolve_fn with the
            resolved value of this promise.
            """
            callback_wrapper(resolve_fn, self._get_value())

        def async_wrapper(resolve_fn: ThenFunc) -> None:
            """Queue resolve_fn to be called after this promise resolves later.

            A wrapper function that will resolve received resolve_fn when this promise
            resolves later.
            """
            self._add_callback(functools.partial(callback_wrapper, resolve_fn))

        if self._is_resolved():
            return Promise(sync_wrapper)
        return Promise(async_wrapper)

    def _do_resolve(self, new_value: Any) -> None:
        # No need to block as we can't change from resolved to unresolved.
        if self.resolved:
            raise RuntimeError("cannot set the value of an already resolved promise")
        with self.mutex:
            self.resolved = True
            self.value = new_value
            for callback in self.callbacks:
                callback(new_value)

    def _add_callback(self, callback: ResolveFunc) -> None:
        with self.mutex:
            self.callbacks.append(callback)

    def _is_resolved(self) -> bool:
        with self.mutex:
            return self.resolved

    def _get_value(self) -> Any:
        with self.mutex:
            return self.value
