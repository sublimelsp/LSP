from __future__ import annotations
from ...protocol import LSPAny
from .protocol import Response
from .types import method2attr
from functools import wraps
from typing import Any, Callable, TypeVar, TYPE_CHECKING
from typing_extensions import ParamSpec

if TYPE_CHECKING:
    from .promise import Promise

__all__ = [
    'APIDecorator',
]

HANDLER_MARKER = '__HANDLER_MARKER'

T = TypeVar('T')
Params = ParamSpec('Params')
# P represents the parameters *after* the 'self' argument
P = TypeVar('P', bound=LSPAny)
R = TypeVar('R', bound=LSPAny)


class APIDecorator:
    """Decorate plugin class methods to handle server initiated requests and notifications.

    1. Ensure plugin class is decorated with `APIDecorator.initialize`.
    2. Add `APIDecorator.request('...')` and/or `APIDecorator.notification('...')` decorates on class methods.

    Notification handlers receive one parameter containing notification parameters.

    Request handlers receive one parameter containing request parameters and return Promise that should be resolved
    with response value. All requests must receive a response.
    """

    @staticmethod
    def initialize(_class: type[T]) -> type[T]:
        original_init = _class.__init__

        @wraps(original_init)
        def init_wrapper(self: T, *args: Params.args, **kwargs: Params.kwargs) -> None:
            original_init(self, *args, **kwargs)
            for attr in dir(self):
                if (func := getattr(self, attr)) and callable(func) and hasattr(func, HANDLER_MARKER):
                    # Set method with transformed name on the class instance.
                    setattr(self, method2attr(getattr(func, HANDLER_MARKER)), func)

        _class.__init__ = init_wrapper
        return _class

    @staticmethod
    def notification_handler(method: str) -> Callable[[Callable[[Any, P], None]], Callable[[Any, P], None]]:
        """Mark the decorated function as a "notification" message handler."""

        def decorator(func: Callable[[Any, P], None]) -> Callable[[Any, P], None]:
            setattr(func, HANDLER_MARKER, method)
            return func

        return decorator

    @staticmethod
    def request_handler(
        method: str
    ) -> Callable[[Callable[[Any, P], Promise[R]]], Callable[[Any, P, int], Promise[Response[Any]]]]:
        """Mark the decorated function as a "request" message handler."""

        def decorator(func: Callable[[Any, P], Promise[R]]) -> Callable[[Any, P, int], Promise[Response[Any]]]:

            @wraps(func)
            def wrapper(self: Any, params: P, request_id: int) -> Promise[Response[Any]]:
                promise = func(self, params)
                return promise.then(lambda result: Response(request_id, result))

            setattr(wrapper, HANDLER_MARKER, method)
            return wrapper

        return decorator
