from .logging import debug, exception_log
from .protocol import Request, Notification, Response
from .transports import StdioTransport, Transport
from .types import Settings
from .typing import Any, Dict, Tuple, Callable, Optional, List
from threading import Condition
import subprocess
import json


TCP_CONNECT_TIMEOUT = 5
DEFAULT_SYNC_REQUEST_TIMEOUT = 1.0


def format_request(payload: Dict[str, Any]) -> str:
    """Converts the request into json"""
    return json.dumps(payload, sort_keys=False, check_circular=False, separators=(',', ':'))


def try_terminate_process(process: subprocess.Popen) -> None:
    try:
        process.terminate()
    except ProcessLookupError:
        pass  # process can be terminated already


class Direction:
    Incoming = '<--'
    Outgoing = '-->'
    OutgoingBlocking = '==>'


class PreformattedPayloadLogger:

    def __init__(self, settings: Settings, server_name: str, sink: Callable[[str], None]) -> None:
        self.settings = settings
        self.server_name = server_name
        self.sink = sink

    def log(self, message: str, params: Any, log_payload: bool) -> None:
        if log_payload:
            message = "{}: {}".format(message, params)
        self.sink(message)

    def format_response(self, direction: str, request_id: int) -> str:
        return "{} {} {}".format(direction, self.server_name, request_id)

    def format_request(self, direction: str, method: str, request_id: int) -> str:
        return "{} {} {}({})".format(direction, self.server_name, method, request_id)

    def format_notification(self, direction: str, method: str) -> str:
        return "{} {} {}".format(direction, self.server_name, method)

    def outgoing_response(self, request_id: int, params: Any) -> None:
        if not self.settings.log_debug:
            return
        self.log(self.format_response(Direction.Outgoing, request_id), params, self.settings.log_payloads)

    def outgoing_request(self, request_id: int, method: str, params: Any, blocking: bool) -> None:
        if not self.settings.log_debug:
            return
        direction = Direction.OutgoingBlocking if blocking else Direction.Outgoing
        self.log(self.format_request(direction, method, request_id), params, self.settings.log_payloads)

    def outgoing_notification(self, method: str, params: Any) -> None:
        if not self.settings.log_debug:
            return
        log_payload = self.settings.log_payloads \
            and method != "textDocument/didChange" \
            and method != "textDocument/didOpen"
        self.log(self.format_notification(Direction.Outgoing, method), params, log_payload)

    def incoming_response(self, request_id: int, params: Any) -> None:
        if not self.settings.log_debug:
            return
        self.log(self.format_response(Direction.Incoming, request_id), params, self.settings.log_payloads)

    def incoming_request(self, request_id: int, method: str, params: Any, unhandled: bool) -> None:
        if not self.settings.log_debug:
            return
        direction = "unhandled" if unhandled else Direction.Incoming
        self.log(self.format_request(direction, method, request_id), params, self.settings.log_payloads)

    def incoming_notification(self, method: str, params: Any, unhandled: bool) -> None:
        if not self.settings.log_debug or method == "window/logMessage":
            return
        direction = "unhandled" if unhandled else Direction.Incoming
        self.log(self.format_notification(direction, method), params, self.settings.log_payloads)


class SyncRequestStatus(object):

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


class Client(object):
    def __init__(self, transport: Transport, settings: Settings) -> None:
        self.transport = transport  # type: Optional[Transport]
        self.transport.start(self.receive_payload, self.on_transport_closed)
        self.request_id = 0
        self.logger = PreformattedPayloadLogger(settings, "server", debug)
        self._response_handlers = {}  # type: Dict[int, Tuple[Optional[Callable], Optional[Callable[[Any], None]]]]
        self._request_handlers = {}  # type: Dict[str, Callable]
        self._notification_handlers = {}  # type: Dict[str, Callable]
        self._sync_request_result = SyncRequestStatus()
        self._sync_request_cvar = Condition()
        self._deferred_notifications = []  # type: List[Any]
        self._deferred_responses = []  # type: List[Tuple[Optional[Callable], Any]]
        self.exiting = False
        self._crash_handler = None  # type: Optional[Callable]
        self._transport_fail_handler = None  # type: Optional[Callable]
        self._error_display_handler = lambda msg: debug(msg)

    def send_request(
            self,
            request: Request,
            handler: Callable[[Optional[Any]], None],
            error_handler: Optional[Callable[[Any], None]] = None,
    ) -> None:
        if self.transport is not None:
            with self._sync_request_cvar:
                self.request_id += 1
                self.logger.outgoing_request(self.request_id, request.method, request.params, blocking=False)
                self._response_handlers[self.request_id] = (handler, error_handler)
                self.send_payload(request.to_payload(self.request_id))
        else:
            debug('unable to send', request.method)
            if error_handler is not None:
                error_handler(None)
            return None

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
        if self.transport is None:
            debug('unable to send', request.method)
            return None

        result = None  # type: Any
        error = None  # type: Optional[Dict[str, Any]]
        exception = None  # type: Optional[Exception]
        with self._sync_request_cvar:
            try:
                self.request_id += 1
                request_id = self.request_id
                self.logger.outgoing_request(request_id, request.method, request.params, blocking=True)
                self._sync_request_result.prepare(request_id)  # After this, is_requesting() returns True.
                self.send_payload(request.to_payload(request_id))
                # We go to sleep. We wake up once another thread calls .notify() on this condition variable.
                self._sync_request_cvar.wait_for(self._sync_request_result.is_ready, timeout)
                if self._sync_request_result.has_error():
                    error = self._sync_request_result.flush_error()
                else:
                    result = self._sync_request_result.flush()
            except KeyError as ex:
                exception = ex
                debug('{}({}): TIMEOUT'.format(request.method, request_id))
            except Exception as ex:
                exception = ex
            finally:
                self._sync_request_result.reset()
            self.flush_deferred_notifications()
            self.flush_deferred_responses()
        if exception is None:
            if error is not None:
                if error_handler is None:
                    self._error_display_handler(error["message"])
                else:
                    error_handler(error)
            else:
                handler(result)

    def flush_deferred_notifications(self) -> None:
        for payload in self._deferred_notifications:
            try:
                handler = self._notification_handlers.get(payload["method"])
                if handler:
                    handler(payload["params"])
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
        if self.transport is not None:
            self.logger.outgoing_notification(notification.method, notification.params)
            self.send_payload(notification.to_payload())
        else:
            debug('unable to send', notification.method)

    def send_response(self, response: Response) -> None:
        self.logger.outgoing_response(response.request_id, response.result)
        self.send_payload(response.to_payload())

    def exit(self) -> None:
        self.exiting = True
        self.send_notification(Notification.exit())

    def set_crash_handler(self, handler: Callable) -> None:
        self._crash_handler = handler

    def set_error_display_handler(self, handler: Callable) -> None:
        self._error_display_handler = handler

    def set_transport_failure_handler(self, handler: Callable) -> None:
        self._transport_fail_handler = handler

    def handle_transport_failure(self) -> None:
        debug('transport failed')
        self.transport = None
        if self._transport_fail_handler is not None:
            self._transport_fail_handler()
        if self._crash_handler is not None:
            self._crash_handler()

    def send_payload(self, payload: Dict[str, Any]) -> None:
        if self.transport:
            message = format_request(payload)
            self.transport.send(message)

    def deduce_payload(
        self,
        payload: Dict[str, Any]
    ) -> Tuple[Optional[Callable], Any, Optional[int], Optional[str], Optional[str]]:
        if "method" in payload:
            method = payload["method"]
            result = payload.get("params")
            if "id" in payload:
                req_id = int(payload["id"])
                tup = (self._request_handlers.get(method), result, req_id, "request", method)
                self.logger.incoming_request(req_id, method, result, tup[0] is None)
                return tup
            else:
                if self._sync_request_result.is_idle():
                    res = (self._notification_handlers.get(method), result, None, "notification", method)
                    self.logger.incoming_notification(method, result, res[0] is None)
                    return res
                else:
                    self._deferred_notifications.append(payload)
        elif "id" in payload:
            response_id = int(payload["id"])
            handler, result = self.response_handler(response_id, payload)
            responetup = (handler, result, None, None, None)
            self.logger.incoming_response(response_id, result)
            return responetup
        else:
            debug("Unknown payload type: ", payload)
        return (None, None, None, None, None)

    def receive_payload(self, message: str) -> None:
        payload = None
        try:
            payload = json.loads(message)
            # limit = min(len(message), 200)
            # debug("got json: ", message[0:limit], "...")
        except IOError as err:
            exception_log("got a non-JSON payload: " + message, err)
            return

        with self._sync_request_cvar:
            handler, result, req_id, typestr, method = self.deduce_payload(payload)

        if handler:
            try:
                assert handler
                if req_id is None:
                    # notification or response
                    handler(result)
                else:
                    # request
                    handler(result, req_id)
            except Exception as err:
                exception_log("Error handling server payload", err)
        elif typestr is not None and method is not None:
            debug("     unhandled", typestr, method)

    def on_transport_closed(self) -> None:
        self._error_display_handler("Communication to server closed, exiting")
        # Differentiate between normal exit and server crash?
        if not self.exiting:
            self.handle_transport_failure()

    def response_handler(self, response_id: int, response: Dict[str, Any]) -> Tuple[Optional[Callable], Any]:
        handler, error_handler = self._response_handlers.pop(response_id, (None, None))
        if "result" in response and "error" not in response:
            return self.handle_response(response_id, handler, response["result"], False)
        elif "result" not in response and "error" in response:
            return self.handle_response(response_id, error_handler, response["error"], True)
        else:
            debug('invalid response payload', response)
            return (None, None)

    def handle_response(self, response_id: int, handler: Optional[Callable],
                        result: Any, is_error: bool) -> Tuple[Optional[Callable], Any]:
        if self._sync_request_result.is_idle():
            pass
        elif self._sync_request_result.is_requesting():
            if self._sync_request_result.request_id() == response_id:
                if is_error:
                    self._sync_request_result.set_error(response_id, result)
                else:
                    self._sync_request_result.set(response_id, result)
                self._sync_request_cvar.notify()
            else:
                self._deferred_responses.append((handler, result))
            return (None, None)
        else:  # self._sync_request_result.is_ready()
            self._deferred_responses.append((handler, result))
            return (None, None)
        if handler:
            return (handler, result)
        elif is_error:
            return (self._error_display_handler, result.get("message"))
        else:
            debug("dropping response with ID", response_id)
            return (None, None)

    def on_request(self, request_method: str, handler: Callable) -> None:
        self._request_handlers[request_method] = handler

    def on_notification(self, notification_method: str, handler: Callable) -> None:
        self._notification_handlers[notification_method] = handler


def attach_stdio_client(process: subprocess.Popen, settings: Settings) -> Client:
    transport = StdioTransport(process)
    client = Client(transport, settings)
    client.set_transport_failure_handler(lambda: try_terminate_process(process))
    return client
