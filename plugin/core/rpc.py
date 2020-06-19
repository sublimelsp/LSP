from .logging import debug, exception_log
from .protocol import Request, Notification, Response, Error, ErrorCode
from .transports import Transport, TransportCallbacks
from .typing import Any, Dict, Tuple, Callable, Optional, List
from abc import ABCMeta, abstractmethod
from threading import Condition, Lock
import sublime

DEFAULT_SYNC_REQUEST_TIMEOUT = 1.0


class Logger(metaclass=ABCMeta):

    @abstractmethod
    def stderr_message(self, message: str) -> None:
        pass

    @abstractmethod
    def outgoing_response(self, request_id: Any, params: Any) -> None:
        pass

    @abstractmethod
    def outgoing_error_response(self, request_id: Any, error: Error) -> None:
        pass

    @abstractmethod
    def outgoing_request(self, request_id: int, method: str, params: Any, blocking: bool) -> None:
        pass

    @abstractmethod
    def outgoing_notification(self, method: str, params: Any) -> None:
        pass

    @abstractmethod
    def incoming_response(self, request_id: int, params: Any, is_error: bool, blocking: bool) -> None:
        pass

    @abstractmethod
    def incoming_request(self, request_id: Any, method: str, params: Any) -> None:
        pass

    @abstractmethod
    def incoming_notification(self, method: str, params: Any, unhandled: bool) -> None:
        pass


class SyncRequestStatus:

    __slots__ = ('__payload', '__error', '__request_id', '__response_id')

    def __init__(self) -> None:
        self.__payload = None  # type: Any
        self.__error = None  # type: Optional[Dict[str, Any]]
        self.__request_id = -1
        self.__response_id = -1

    def prepare(self, request_id: int) -> None:
        assert self.is_idle()
        assert self.__payload is None
        assert self.__error is None
        self.__request_id = request_id

    def request_id(self) -> int:
        assert not self.is_idle()
        return self.__request_id

    def set(self, response_id: int, payload: Any) -> None:
        assert self.is_requesting()
        assert self.__request_id == response_id
        self.__payload = payload
        self.__response_id = response_id
        assert self.is_ready()

    def set_error(self, response_id: int, error: Dict[str, Any]) -> None:
        assert self.is_requesting()
        assert self.__request_id == response_id
        self.__error = error
        self.__response_id = response_id
        assert self.is_ready()

    def is_ready(self) -> bool:
        return self.__request_id != -1 and self.__request_id == self.__response_id

    def is_requesting(self) -> bool:
        return self.__request_id != -1 and self.__response_id == -1

    def is_idle(self) -> bool:
        return self.__request_id == -1

    def has_error(self) -> bool:
        return self.__error is not None

    def flush(self) -> Any:
        assert not self.has_error()
        assert self.is_ready()
        result = self.__payload
        self.reset()
        return result

    def flush_error(self) -> Dict[str, Any]:
        assert self.__error is not None
        assert self.is_ready()
        result = self.__error
        self.reset()
        return result

    def reset(self) -> None:
        self.__payload = None
        self.__request_id = -1
        self.__response_id = -1


def print_to_status_bar(error: Dict[str, Any]) -> None:
    sublime.status_message(error["message"])


def method2attr(method: str) -> str:
    # window/messageRequest -> m_window_messageRequest
    # $/progress -> m___progress
    # client/registerCapability -> m_client_registerCapability
    return 'm_' + ''.join(map(lambda c: c if c.isalpha() else '_', method))


class Client(TransportCallbacks):
    def __init__(self, logger: Logger) -> None:
        self.transport = None  # type: Optional[Transport]
        self.request_id = 0  # Our request IDs are always integers.
        self._logger = logger
        self._response_handlers = {}  # type: Dict[int, Tuple[Callable, Optional[Callable[[Any], None]]]]
        self._sync_request_result = SyncRequestStatus()
        self._sync_request_lock = Lock()
        self._sync_request_cvar = Condition(self._sync_request_lock)
        self._deferred_notifications = []  # type: List[Any]
        self._deferred_responses = []  # type: List[Tuple[Optional[Callable], Any]]

    def send_request(
            self,
            request: Request,
            handler: Callable[[Optional[Any]], None],
            error_handler: Optional[Callable[[Any], None]] = None,
    ) -> None:
        with self._sync_request_cvar:
            self.request_id += 1
            request_id = self.request_id
            self._response_handlers[request_id] = (handler, error_handler)
        self._logger.outgoing_request(request_id, request.method, request.params, blocking=False)
        self.send_payload(request.to_payload(request_id))

    def execute_request(
            self,
            request: Request,
            handler: Callable[[Optional[Any]], None],
            error_handler: Optional[Callable[[Any], None]] = None,
            timeout: float = DEFAULT_SYNC_REQUEST_TIMEOUT
    ) -> None:
        """
        Sends a request and waits for response up to timeout (default: 1 second), blocking the current thread.
        """
        result = None  # type: Any
        error = None  # type: Optional[Dict[str, Any]]
        exception = None  # type: Optional[Exception]
        with self._sync_request_cvar:
            try:
                self.request_id += 1
                request_id = self.request_id
                self._logger.outgoing_request(request_id, request.method, request.params, blocking=True)
                self._sync_request_result.prepare(request_id)  # After this, is_requesting() returns True.
                self.send_payload(request.to_payload(request_id))
                self._response_handlers[request_id] = (handler, error_handler)
                # We go to sleep. We wake up once another thread calls .notify() on this condition variable.
                if not self._sync_request_cvar.wait_for(self._sync_request_result.is_ready, timeout):
                    error = {"code": ErrorCode.Timeout, "message": "timeout on {}".format(request.method)}
                elif self._sync_request_result.has_error():
                    error = self._sync_request_result.flush_error()
                else:
                    result = self._sync_request_result.flush()
            except Exception as ex:
                exception = ex
            finally:
                self._sync_request_result.reset()
            self.flush_deferred_notifications()
            self.flush_deferred_responses()
        if exception is None:
            if error is not None:
                if not error_handler:
                    error_handler = print_to_status_bar
                error_handler(error)
            else:
                handler(result)

    def flush_deferred_notifications(self) -> None:
        for payload in self._deferred_notifications:
            try:
                method = payload["method"]
                handler = self._get_handler(method)
                result = payload["params"]
                self._logger.incoming_notification(method, result, handler is None)
                if handler:
                    handler(result)
            except Exception as err:
                exception_log("Error handling server payload", err)
        self._deferred_notifications.clear()

    def flush_deferred_responses(self) -> None:
        for handler, result in self._deferred_responses:
            if handler:
                try:
                    handler(result)
                except Exception as err:
                    exception_log("Error handling server payload", err)
        self._deferred_responses.clear()

    def send_notification(self, notification: Notification) -> None:
        self._logger.outgoing_notification(notification.method, notification.params)
        self.send_payload(notification.to_payload())

    def send_response(self, response: Response) -> None:
        self._logger.outgoing_response(response.request_id, response.result)
        self.send_payload(response.to_payload())

    def send_error_response(self, request_id: Any, error: Error) -> None:
        self._logger.outgoing_error_response(request_id, error)
        self.send_payload({'jsonrpc': '2.0', 'id': request_id, 'error': error.to_lsp()})

    def exit(self) -> None:
        self.send_notification(Notification.exit())
        try:
            self.transport.close()  # type: ignore
        except AttributeError:
            pass

    def send_payload(self, payload: Dict[str, Any]) -> None:
        try:
            self.transport.send(payload)  # type: ignore
        except AttributeError:
            pass

    def deduce_payload(
        self,
        payload: Dict[str, Any]
    ) -> Tuple[Optional[Callable], Any, Optional[int], Optional[str], Optional[str]]:
        if "method" in payload:
            method = payload["method"]
            handler = self._get_handler(method)
            result = payload.get("params")
            if "id" in payload:
                req_id = payload["id"]
                self._logger.incoming_request(req_id, method, result)
                if handler is None:
                    self.send_error_response(req_id, Error(ErrorCode.MethodNotFound, method))
                else:
                    tup = (handler, result, req_id, "request", method)
                    return tup
            else:
                if self._sync_request_result.is_idle():
                    res = (handler, result, None, "notification", method)
                    self._logger.incoming_notification(method, result, res[0] is None)
                    return res
                else:
                    self._deferred_notifications.append(payload)
        elif "id" in payload:
            response_id = int(payload["id"])
            handler, result, is_error = self.response_handler(response_id, payload)
            response_tuple = (handler, result, None, None, None)
            blocking = self._sync_request_result.is_ready()
            self._logger.incoming_response(response_id, result, is_error, blocking)
            return response_tuple
        else:
            debug("Unknown payload type: ", payload)
        return (None, None, None, None, None)

    def on_payload(self, payload: Dict[str, Any]) -> None:
        with self._sync_request_cvar:
            handler, result, req_id, typestr, method = self.deduce_payload(payload)

        if handler:
            try:
                if req_id is None:
                    # notification or response
                    handler(result)
                else:
                    # request
                    try:
                        handler(result, req_id)
                    except Error as err:
                        self.send_error_response(req_id, err)
                    except Exception as ex:
                        self.send_error_response(req_id, Error.from_exception(ex))
                        raise
            except Exception as err:
                exception_log("Error handling {}".format(typestr), err)

    def on_stderr_message(self, message: str) -> None:
        pass

    def on_transport_close(self, exit_code: int, exception: Optional[Exception]) -> None:
        self.transport = None

    def response_handler(self, response_id: int, response: Dict[str, Any]) -> Tuple[Optional[Callable], Any, bool]:
        handler, error_handler = self._response_handlers.pop(response_id, (None, None))
        if not handler:
            error = {"code": ErrorCode.InvalidParams, "message": "unknown response ID {}".format(response_id)}
            return self.handle_response(response_id, print_to_status_bar, error, True)
        if "result" in response and "error" not in response:
            return self.handle_response(response_id, handler, response["result"], False)
        if not error_handler:
            error_handler = print_to_status_bar
        if "result" not in response and "error" in response:
            error = response["error"]
        else:
            error = {"code": ErrorCode.InvalidParams, "message": "invalid response payload"}
        return self.handle_response(response_id, error_handler, error, True)

    def handle_response(self, response_id: int, handler: Callable,
                        result: Any, is_error: bool) -> Tuple[Optional[Callable], Any, bool]:
        if self._sync_request_result.is_idle():
            return (handler, result, is_error)
        elif self._sync_request_result.is_requesting():
            if self._sync_request_result.request_id() == response_id:
                if is_error:
                    self._sync_request_result.set_error(response_id, result)
                else:
                    self._sync_request_result.set(response_id, result)
                self._sync_request_cvar.notify()
            else:
                self._deferred_responses.append((handler, result))
            return (None, result, is_error)
        else:  # self._sync_request_result.is_ready()
            self._deferred_responses.append((handler, result))
            return (None, None, is_error)

    def _get_handler(self, method: str) -> Optional[Callable]:
        return getattr(self, method2attr(method), None)
