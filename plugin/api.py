from __future__ import annotations

from ..protocol import LSPAny
from .core.protocol import Response
from .core.types import method2attr
from functools import wraps
from typing import Any, Callable, TYPE_CHECKING, TypeVar
import inspect

if TYPE_CHECKING:
    from .core.promise import Promise

__all__ = [
    'APIHandler',
    'notification_handler',
    'request_handler',
]

HANDLER_MARKER = '__HANDLER_MARKER'

# P represents the parameters *after* the 'self' argument
P = TypeVar('P', bound=LSPAny)
R = TypeVar('R', bound=LSPAny)


class APIHandler:
    """Trigger initialization of decorated API methods."""

    def __init__(self) -> None:
        super().__init__()
        for _, method in inspect.getmembers(self, inspect.ismethod):
            if hasattr(method, HANDLER_MARKER):
                # Set method with transformed name on the class instance.
                setattr(self, method2attr(getattr(method, HANDLER_MARKER)), method)


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
        def on_open_doc(self, params: TextDocumentIdentifier) -> Promise[bool]:
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
