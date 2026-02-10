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
    'initialize_api_decorators',
    'notification_handler',
    'request_handler',
]

HANDLER_MARKER = '__HANDLER_MARKER'

T = TypeVar('T')
Params = ParamSpec('Params')
# P represents the parameters *after* the 'self' argument
P = TypeVar('P', bound=LSPAny)
R = TypeVar('R', bound=LSPAny)


def initialize_api_decorators(_class: type[T]) -> type[T]:
    """Internal decorator used for processing decorated methods."""

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


def notification_handler(method: str) -> Callable[[Callable[[Any, P], None]], Callable[[Any, P], None]]:
    """Decorator to mark a method as a handler for a specific LSP notification.

    Usage:
        ```py
        @notification_handler('eslint/status')
        def on_eslint_status(self, params: str) -> None:
            ...
        ```

    The decorated method will be called with the notification parameters whenever the specified
    notification is received from the language server. Notification handlers do not return a value.

    :param      method:             The LSP notification method name (e.g., 'eslint/status').
    :returns:   A decorator that registers the function as a notification handler.
    """

    def decorator(func: Callable[[Any, P], None]) -> Callable[[Any, P], None]:
        setattr(func, HANDLER_MARKER, method)
        return func

    return decorator


def request_handler(
    method: str
) -> Callable[[Callable[[Any, P], Promise[R]]], Callable[[Any, P, int], Promise[Response[R]]]]:
    """Decorator to mark a method as a handler for a specific LSP request.

    Usage:
        ```py
        @request_handler('eslint/openDoc')
        def on_hover(self, params: TextDocumentIdentifier) -> Promise[bool]:
            ...
        ```

    The decorated method will be called with the request parameters whenever the specified
    request is received from the language server. The method must return a Promise that resolves
    to the response value. The framework will automatically send it back to the server.

    :param      method:             The LSP request method name (e.g., 'eslint/openDoc').
    :returns:   A decorator that registers the function as a request handler.
    """

    def decorator(func: Callable[[Any, P], Promise[R]]) -> Callable[[Any, P, int], Promise[Response[R]]]:

        @wraps(func)
        def wrapper(self: Any, params: P, request_id: int) -> Promise[Response[Any]]:
            promise = func(self, params)
            return promise.then(lambda result: Response(request_id, result))

        setattr(wrapper, HANDLER_MARKER, method)
        return wrapper

    return decorator
