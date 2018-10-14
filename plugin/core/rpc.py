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

from .logging import debug, exception_log, server_log
from .protocol import Request, Notification
from .types import Settings


TCP_CONNECT_TIMEOUT = 5

# RequestDict = TypedDict('RequestDict', {'id': 'Union[str,int]', 'method': str, 'params': 'Optional[Any]'})


def format_request(payload: 'Dict[str, Any]') -> str:
    """Converts the request into json and adds the Content-Length header"""
    content = json.dumps(payload, sort_keys=False)
    content_length = len(content)
    result = "Content-Length: {}\r\n\r\n{}\r\n".format(content_length, content)
    return result


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
        except ConnectionRefusedError as e:
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


class Client(object):
    def __init__(self, transport: Transport, settings) -> None:
        self.transport = transport
        self.transport.start(self.receive_payload, self.on_transport_closed)
        self.request_id = 0
        self._response_handlers = {}  # type: Dict[int, Callable]
        self._error_handlers = {}  # type: Dict[int, Callable]
        self._request_handlers = {}  # type: Dict[str, Callable]
        self._notification_handlers = {}  # type: Dict[str, Callable]
        self.exiting = False
        self._crash_handler = None  # type: Optional[Callable]
        self._transport_fail_handler = None  # type: Optional[Callable]
        self._error_display_handler = lambda msg: debug(msg)
        self.settings = settings

    def send_request(self, request: Request, handler: 'Callable[[Optional[Any]], None]',
                     error_handler: 'Optional[Callable]' = None) -> None:
        self.request_id += 1
        debug(' --> ' + request.method)
        if handler is not None:
            self._response_handlers[self.request_id] = handler
        if error_handler is not None:
            self._error_handlers[self.request_id] = error_handler
        self.send_payload(request.to_payload(self.request_id))

    def send_notification(self, notification: Notification) -> None:
        debug(' --> ' + notification.method)
        self.send_payload(notification.to_payload())

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
        if self._transport_fail_handler is not None:
            self._transport_fail_handler()
        if self._crash_handler is not None:
            self._crash_handler()

    def send_payload(self, payload: 'Dict[str, Any]') -> None:
        message = format_request(payload)
        self.transport.send(message)

    def receive_payload(self, message: str) -> None:
        payload = None
        try:
            payload = json.loads(message)
            # limit = min(len(message), 200)
            # debug("got json: ", message[0:limit], "...")
        except IOError as err:
            exception_log("got a non-JSON payload: " + message, err)
            return

        try:
            if "method" in payload:
                if "id" in payload:
                    self.request_handler(payload)
                else:
                    self.notification_handler(payload)
            elif "id" in payload:
                self.response_handler(payload)
            else:
                debug("Unknown payload type: ", payload)
        except Exception as err:
            exception_log("Error handling server payload", err)

    def on_transport_closed(self) -> None:
        self._error_display_handler("Communication to server closed, exiting")
        # Differentiate between normal exit and server crash?
        if not self.exiting:
            self.handle_transport_failure()

    def response_handler(self, response: 'Dict[str, Any]') -> None:
        handler_id = int(response["id"])  # dotty sends strings back :(
        if 'result' in response and 'error' not in response:
            result = response['result']
            if self.settings.log_payloads:
                debug('     ' + str(result))
            if handler_id in self._response_handlers:
                self._response_handlers[handler_id](result)
            else:
                debug("No handler found for id " + str(response.get("id")))
        elif 'error' in response and 'result' not in response:
            error = response['error']
            if self.settings.log_payloads:
                debug('     ' + str(error))
            if handler_id in self._error_handlers:
                self._error_handlers[handler_id](error)
            else:
                self._error_display_handler(error.get("message"))
        else:
            debug('invalid response payload', response)

    def on_request(self, request_method: str, handler: 'Callable') -> None:
        self._request_handlers[request_method] = handler

    def on_notification(self, notification_method: str, handler: 'Callable') -> None:
        self._notification_handlers[notification_method] = handler

    def request_handler(self, request: 'Dict[str, Any]') -> None:
        params = request.get("params", dict())
        method = request.get("method", '')
        debug('<--  ' + method)
        if self.settings.log_payloads and params:
            debug('     ' + str(params))
        if method in self._request_handlers:
            try:
                self._request_handlers[method](params)
            except Exception as err:
                exception_log("Error handling request " + method, err)
        else:
            debug("Unhandled request", method)

    def notification_handler(self, notification: 'Dict[str, Any]') -> None:
        method = notification["method"]
        params = notification.get("params")
        if method == "window/logMessage":
            debug('<--  ' + method)
            server_log(params.get("message", "???") if params else "???")
            return

        debug('<--  ' + method)
        if self.settings.log_payloads and params:
            debug('     ' + str(params))
        if method in self._notification_handlers:
            try:
                self._notification_handlers[method](params)
            except Exception as err:
                exception_log("Error handling notification " + method, err)
        else:
            debug("Unhandled notification:", method)
