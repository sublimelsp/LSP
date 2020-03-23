from .logging import debug, exception_log
from .protocol import Request, Notification, Response, Error, ErrorCode
from .transports import StdioTransport, Transport
from .types import Settings
from .typing import Any, Dict, Tuple, Callable, Optional, Mapping
from threading import Condition
from threading import Lock
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


class PreformattedPayloadLogger:

    def __init__(self, settings: Settings, server_name: str, sink: Callable[[str], None]) -> None:
        self.settings = settings
        self.server_name = server_name
        self.sink = sink

    def log(self, message: str, params: Any, log_payload: bool) -> None:
        if log_payload:
            message = "{}: {}".format(message, params)
        self.sink(message)

    def format_response(self, direction: str, request_id: Any) -> str:
        return "{} {} {}".format(direction, self.server_name, request_id)

    def format_request(self, direction: str, method: str, request_id: Any) -> str:
        return "{} {} {}({})".format(direction, self.server_name, method, request_id)

    def format_notification(self, direction: str, method: str) -> str:
        return "{} {} {}".format(direction, self.server_name, method)

    def outgoing_response(self, request_id: Any, params: Any) -> None:
        if not self.settings.log_debug:
            return
        self.log(self.format_response(">>>", request_id), params, self.settings.log_payloads)

    def outgoing_error_response(self, request_id: Any, error: Error) -> None:
        if not self.settings.log_debug:
            return
        self.log(self.format_response("~~>", request_id), error.to_lsp(), self.settings.log_payloads)

    def outgoing_request(self, request_id: int, method: str, params: Any, blocking: bool) -> None:
        if not self.settings.log_debug:
            return
        direction = "==>" if blocking else "-->"
        self.log(self.format_request(direction, method, request_id), params, self.settings.log_payloads)

    def outgoing_notification(self, method: str, params: Any) -> None:
        if not self.settings.log_debug:
            return
        # Do not log the payloads if any of these conditions occur because the payloads might contain the entire
        # content of the view.
        log_payload = self.settings.log_payloads \
            and method != "textDocument/didChange" \
            and method != "textDocument/didOpen"
        if log_payload and method == "textDocument/didSave" and isinstance(params, dict) and "text" in params:
            log_payload = False
        self.log(self.format_notification(" ->", method), params, log_payload)

    def incoming_response(self, request_id: int, params: Any) -> None:
        if not self.settings.log_debug:
            return
        self.log(self.format_response("<<<", request_id), params, self.settings.log_payloads)

    def incoming_error_response(self, request_id: Any, error: Any) -> None:
        if not self.settings.log_debug:
            return
        self.log(self.format_response('<~~', request_id), error, self.settings.log_payloads)

    def incoming_request(self, request_id: Any, method: str, params: Any) -> None:
        if not self.settings.log_debug:
            return
        self.log(self.format_request("<--", method, request_id), params, self.settings.log_payloads)

    def incoming_notification(self, method: str, params: Any, unhandled: bool) -> None:
        if not self.settings.log_debug or method == "window/logMessage":
            return
        direction = "<? " if unhandled else "<- "
        self.log(self.format_notification(direction, method), params, self.settings.log_payloads)


class Client(object):
    def __init__(self, transport: Transport, settings: Settings) -> None:
        self.transport = transport  # type: Optional[Transport]
        self.transport.start(self.receive_payload, self.on_transport_closed)
        self.request_id = 0  # Our request IDs are always integers.
        self.logger = PreformattedPayloadLogger(settings, "server", debug)
        self._response_handlers = {}  # type: Dict[int, Tuple[Optional[Callable], Optional[Callable[[Any], None]]]]
        self._request_handlers = {}  # type: Dict[str, Callable]
        self._notification_handlers = {}  # type: Dict[str, Callable]
        self._sync_request_results = {}  # type: Dict[int, Optional[Any]]
        self._sync_request_lock = Lock()
        self._sync_request_cvar = Condition(self._sync_request_lock)
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
        self.request_id += 1
        if self.transport is not None:
            self.logger.outgoing_request(self.request_id, request.method, request.params, blocking=False)
            self._response_handlers[self.request_id] = (handler, error_handler)
            self.send_payload(request.to_payload(self.request_id))
        else:
            debug('unable to send', request.method)
            if error_handler is not None:
                error_handler(None)
            return None

    def execute_request(self, request: Request, timeout: float = DEFAULT_SYNC_REQUEST_TIMEOUT) -> Optional[Any]:
        """
        Sends a request and waits for response up to timeout (default: 1 second), blocking the current thread.
        """
        if self.transport is None:
            debug('unable to send', request.method)
            return None

        self.request_id += 1
        request_id = self.request_id
        self.logger.outgoing_request(request_id, request.method, request.params, blocking=True)
        self.send_payload(request.to_payload(request_id))
        result = None
        try:
            with self._sync_request_cvar:
                # We go to sleep. We wake up once another thread calls .notify() on this condition variable.
                self._sync_request_cvar.wait_for(lambda: request_id in self._sync_request_results, timeout)
                result = self._sync_request_results.pop(request_id)
        except KeyError:
            debug('timeout on', request.method)
            return None
        return result

    def send_notification(self, notification: Notification) -> None:
        if self.transport is not None:
            self.logger.outgoing_notification(notification.method, notification.params)
            self.send_payload(notification.to_payload())
        else:
            debug('unable to send', notification.method)

    def send_response(self, response: Response) -> None:
        self.logger.outgoing_response(response.request_id, response.result)
        self.send_payload(response.to_payload())

    def send_error_response(self, request_id: Any, error: Error) -> None:
        self.logger.outgoing_error_response(request_id, error)
        self.send_payload({'jsonrpc': '2.0', 'id': request_id, 'error': error.to_lsp()})

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
                self.request_or_notification_handler(payload)
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

    def response_handler(self, response: Dict[str, Any]) -> None:
        # This response handler *must not* run from the same thread that does a sync request
        # because of the usage of the condition variable below.
        request_id = int(response["id"])
        handler, error_handler = self._response_handlers.pop(request_id, (None, None))
        if "result" in response and "error" not in response:
            result = response["result"]
            self.logger.incoming_response(request_id, result)
            if handler:
                handler(result)
            else:
                with self._sync_request_cvar:
                    self._sync_request_results[request_id] = result
                    # At most one thread is waiting on the result.
                    self._sync_request_cvar.notify()
        elif "result" not in response and "error" in response:
            error = response["error"]
            self.logger.incoming_error_response(request_id, error)
            if error_handler:
                error_handler(error)
            else:
                self._error_display_handler(error.get("message"))
        else:
            debug('invalid response payload', response)

    def on_request(self, request_method: str, handler: Callable) -> None:
        self._request_handlers[request_method] = handler

    def on_notification(self, notification_method: str, handler: Callable) -> None:
        self._notification_handlers[notification_method] = handler

    def request_or_notification_handler(self, payload: Mapping[str, Any]) -> None:
        method = payload["method"]  # type: str
        params = payload.get("params")
        # Server request IDs can be either a string or an int.
        request_id = payload.get("id")
        if request_id is not None:
            handler = self._request_handlers.get(method)
            self.logger.incoming_request(request_id, method, params)
            if handler:
                try:
                    handler(params, request_id)
                except Error as error:
                    # The request handler raised this exception on purpose, so don't log this exception.
                    self.send_error_response(request_id, error)
                except Exception as ex:
                    # The request handler didn't raise this exception on purpose, so log the exception.
                    exception_log("Error handling request {}".format(method), ex)
                    self.send_error_response(request_id, Error.from_exception(ex))
            else:
                self.send_error_response(request_id, Error(ErrorCode.MethodNotFound, method))
        else:
            handler = self._notification_handlers.get(method)
            if handler:
                try:
                    handler(params)
                    self.logger.incoming_notification(method, params, unhandled=False)
                except Exception as err:
                    exception_log("Error handling notification {}".format(method), err)
                    self.logger.incoming_notification(method, params, unhandled=True)
            else:
                self.logger.incoming_notification(method, params, unhandled=True)


def attach_stdio_client(process: subprocess.Popen, settings: Settings) -> Client:
    transport = StdioTransport(process)
    client = Client(transport, settings)
    client.set_transport_failure_handler(lambda: try_terminate_process(process))
    return client
