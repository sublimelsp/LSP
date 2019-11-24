import json
import socket
import time
from .transports import TCPTransport, StdioTransport, Transport
from .process import attach_logger
try:
    import subprocess
    from typing import Any, List, Dict, Tuple, Callable, Optional, Union
    # from mypy_extensions import TypedDict
    assert Any and List and Dict and Tuple and Callable and Optional and Union and subprocess
except ImportError:
    pass

from .logging import debug, exception_log
from .protocol import Request, Notification, Response
from .types import Settings
from threading import Condition

TCP_CONNECT_TIMEOUT = 5
DEFAULT_SYNC_REQUEST_TIMEOUT = 1.0

# RequestDict = TypedDict('RequestDict', {'id': 'Union[str,int]', 'method': str, 'params': 'Optional[Any]'})


def format_request(payload: 'Dict[str, Any]') -> str:
    """Converts the request into json"""
    return json.dumps(payload, sort_keys=False)


def attach_tcp_client(tcp_port: int, process: 'subprocess.Popen', settings: Settings) -> 'Optional[Client]':
    if settings.log_stderr:
        attach_logger(process, process.stdout)

    host = "localhost"
    start_time = time.time()
    debug('connecting to {}:{}'.format(host, tcp_port))

    while time.time() - start_time < TCP_CONNECT_TIMEOUT:
        try:
            sock = socket.create_connection((host, tcp_port))
            transport = TCPTransport(sock)

            client = Client(transport, settings)
            client.set_transport_failure_handler(lambda: try_terminate_process(process))
            return client
        except ConnectionRefusedError:
            pass

    process.kill()
    raise Exception("Timeout connecting to socket")


def attach_stdio_client(process: 'subprocess.Popen', settings: Settings) -> 'Client':
    transport = StdioTransport(process)

    # TODO: process owner can take care of this outside client?
    if settings.log_stderr:
        attach_logger(process, process.stderr)
    client = Client(transport, settings)
    client.set_transport_failure_handler(lambda: try_terminate_process(process))
    return client


def try_terminate_process(process: 'subprocess.Popen') -> None:
    try:
        process.terminate()
    except ProcessLookupError:
        pass  # process can be terminated already


class SyncRequestStatus(object):

    IDLE = 0
    REQUESTING = 1
    READY = 2

    __slots__ = ('__state', '__payload', '__request_id', '__response_id')

    def __init__(self) -> None:
        self.__state = self.IDLE
        self.__payload = None  # type: Any
        self.__request_id = -1
        self.__response_id = -1

    def prepare(self, request_id: int) -> None:
        assert self.__state == self.IDLE
        assert self.__payload is None
        assert self.__request_id == -1
        self.__state = self.REQUESTING
        self.__request_id = request_id

    def request_id(self) -> int:
        assert self.__request_id != -1
        return self.__request_id

    def set(self, response_id: int, payload: 'Any') -> None:
        assert self.__state == self.REQUESTING
        assert self.__request_id == response_id
        self.__state = self.READY
        self.__payload = payload
        self.__response_id = response_id

    def is_ready(self) -> bool:
        return self.__state == self.READY

    def is_requesting(self) -> bool:
        return self.__state == self.REQUESTING

    def is_idle(self) -> bool:
        return self.__state == self.IDLE

    def flush(self) -> 'Tuple[int, Any]':
        # assert self.__state == self.READY
        result = (self.__response_id, self.__payload)
        self.reset()
        return result

    def reset(self) -> None:
        self.__state = self.IDLE
        self.__payload = None
        self.__request_id = -1
        self.__response_id = -1


class Client(object):
    def __init__(self, transport: Transport, settings: Settings) -> None:
        self.transport = transport  # type: Optional[Transport]
        self.transport.start(self.receive_payload, self.on_transport_closed)
        self.request_id = 0
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
        self.settings = settings

    def send_request(
            self,
            request: Request,
            handler: 'Callable[[Optional[Any]], None]',
            error_handler: 'Optional[Callable[[Any], None]]' = None,
    ) -> 'None':
        if self.transport is not None:
            with self._sync_request_cvar:
                self.request_id += 1
                debug(' --> {}({})'.format(request.method, self.request_id))
                self._response_handlers[self.request_id] = (handler, error_handler)
                self.send_payload(request.to_payload(self.request_id))
        else:
            debug('unable to send', request.method)
            if error_handler is not None:
                error_handler(None)
            return None

    def execute_request(self, request: Request, timeout: float = DEFAULT_SYNC_REQUEST_TIMEOUT) -> 'Optional[Any]':
        """
        Sends a request and waits for response up to timeout (default: 1 second), blocking the current thread.
        """
        if self.transport is None:
            debug('unable to send', request.method)
            return None

        with self._sync_request_cvar:
            try:
                self.request_id += 1
                request_id = self.request_id
                debug(' ==> {}({}): begin'.format(request.method, request_id))
                self._sync_request_result.prepare(request_id)  # After this, is_requesting() returns True.
                self.send_payload(request.to_payload(request_id))
                # We go to sleep. We wake up once another thread calls .notify() on this condition variable.
                self._sync_request_cvar.wait_for(self._sync_request_result.is_ready, timeout)
                response_id, result = self._sync_request_result.flush()
                assert response_id == request_id
                debug('     {}({}): end'.format(request.method, request_id))
                return result
            except KeyError:
                debug('     {}({}): TIMEOUT'.format(request.method, request_id))
                self._sync_request_result.reset()
            except Exception as ex:
                exception_log('          {}({}): ERROR'.format(request.method, request_id), ex)
                self._sync_request_result.reset()
            finally:
                self.flush_deferred_notifications()
                self.flush_deferred_responses()
        return None

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
            debug(' -->', notification.method)
            self.send_payload(notification.to_payload())
        else:
            debug('unable to send', notification.method)

    def send_response(self, response: Response) -> None:
        self.send_payload(response.to_payload())

    def exit(self) -> None:
        self.exiting = True
        self.send_notification(Notification.exit())

    def set_crash_handler(self, handler: 'Callable') -> None:
        self._crash_handler = handler

    def set_error_display_handler(self, handler: 'Callable') -> None:
        self._error_display_handler = handler

    def set_transport_failure_handler(self, handler: 'Callable') -> None:
        self._transport_fail_handler = handler

    def handle_transport_failure(self) -> None:
        debug('transport failed')
        self.transport = None
        if self._transport_fail_handler is not None:
            self._transport_fail_handler()
        if self._crash_handler is not None:
            self._crash_handler()

    def send_payload(self, payload: 'Dict[str, Any]') -> None:
        if self.transport:
            message = format_request(payload)
            self.transport.send(message)

    def deduce_payload(self, payload: 'Dict[str, Any]') -> 'Tuple[Optional[Callable], Any, Optional[int]]':
        if "method" in payload:
            method = payload["method"]
            result = payload.get("params")
            if "id" in payload:
                req_id = int(payload["id"])
                debug('<--  {}({})'.format(method, req_id))
                if self.settings.log_payloads:
                    debug('<<< {}:'.format(req_id), result)
                return (self._request_handlers.get(method), result, req_id)
            else:
                if method != "window/logMessage":
                    debug('<-- ', method)
                if self.settings.log_payloads:
                    debug('<<< ', payload)
                if self._sync_request_result.is_idle():
                    return (self._notification_handlers.get(method), result, None)
                else:
                    self._deferred_notifications.append(payload)
        elif "id" in payload:
            try:
                response_id = int(payload["id"])
                handler, result = self.response_handler(response_id, payload)
                return (handler, result, None)
            except AssertionError as err:
                exception_log("Programmer error", err)
        else:
            debug("Unknown payload type: ", payload)
        return (None, None, None)

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
            handler, result, req_id = self.deduce_payload(payload)
        if handler:
            try:
                if req_id is None:
                    # notification or response
                    handler(result)
                else:
                    # request
                    handler(result, req_id)
            except Exception as err:
                exception_log("Error handling server payload", err)

    def on_transport_closed(self) -> None:
        self._error_display_handler("Communication to server closed, exiting")
        # Differentiate between normal exit and server crash?
        if not self.exiting:
            self.handle_transport_failure()

    def response_handler(self, response_id: int, response: 'Dict[str, Any]') -> 'Tuple[Optional[Callable], Any]':
        if self.settings.log_payloads:
            debug('<<<  {}:'.format(response_id), response.get("result", None))
        handler, error_handler = self._response_handlers.pop(response_id, (None, None))
        if "result" in response and "error" not in response:
            return self.handle_response_result(response_id, handler, response["result"])
        elif "result" not in response and "error" in response:
            return self.handle_response_error(error_handler, response["error"])
        else:
            debug('invalid response payload', response)
            return (None, None)

    def handle_response_result(self, response_id: int, handler: 'Optional[Callable]',
                               result: 'Any') -> 'Tuple[Optional[Callable], Any]':
        if self._sync_request_result.is_idle():
            pass
        elif self._sync_request_result.is_requesting():
            if self._sync_request_result.request_id() == response_id:
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
        else:
            debug("dropping response with ID", response_id)
            return (None, None)

    def handle_response_error(self, error_handler: 'Optional[Callable]',
                              error: 'Any') -> 'Tuple[Optional[Callable], Any]':
        if self.settings.log_payloads:
            debug('ERR: ' + str(error))
        if error_handler:
            return (error_handler, error)
        else:
            return (self._error_display_handler, error.get("message"))

    def on_request(self, request_method: str, handler: 'Callable') -> None:
        self._request_handlers[request_method] = handler

    def on_notification(self, notification_method: str, handler: 'Callable') -> None:
        self._notification_handlers[notification_method] = handler
