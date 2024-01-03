from abc import ABCMeta, abstractmethod
from LSP.plugin.core.typing import Any, Callable

__all__ = ['ApiWrapperInterface']


NotificationHandler = Callable[[Any], None]
RequestHandler = Callable[[Any, Callable[[Any], None]], None]


class ApiWrapperInterface(metaclass=ABCMeta):
    """
    An interface for sending and receiving requests and notifications from and to the server. An implementation of it
    is available through the :func:`GenericClientHandler.on_ready()` override.
    """

    @abstractmethod
    def on_notification(self, method: str, handler: NotificationHandler) -> None:
        """
        Registers a handler for given notification name. The handler will be called with optional params.
        """
        ...

    @abstractmethod
    def on_request(self, method: str, handler: RequestHandler) -> None:
        """
        Registers a handler for given request name. The handler will be called with two arguments - first the params
        sent with the request and second the function that must be used to respond to the request. The response
        function takes params to respond with.
        """
        ...

    @abstractmethod
    def send_notification(self, method: str, params: Any) -> None:
        """
        Sends a notification to the server.
        """
        ...

    @abstractmethod
    def send_request(self, method: str, params: Any, handler: Callable[[Any, bool], None]) -> None:
        """
        Sends a request to the server. The handler will be called with the result received from the server and
        a boolean value `False` if request has succeeded and `True` if it returned an error.
        """
        ...
