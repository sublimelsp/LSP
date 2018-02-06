import json
import sublime
import threading
import socket
import time
from abc import ABCMeta, abstractmethod

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass

from .settings import settings, log
from .protocol import Request, Notification


ContentLengthHeader = b"Content-Length: "
TCP_CONNECT_TIMEOUT = 5


def format_request(payload: 'Dict[str, Any]'):
    """Converts the request into json and adds the Content-Length header"""
    content = json.dumps(payload, sort_keys=False)
    content_length = len(content)
    result = "Content-Length: {}\r\n\r\n{}".format(content_length, content)
    return result


def attach_tcp_client(tcp_port, process, project_path):
    if settings.log_stderr:
        attach_logger(process, process.stdout)

    host = "localhost"
    start_time = time.time()
    log(2, 'connecting to %s:%s', host, tcp_port)

    while time.time() - start_time < TCP_CONNECT_TIMEOUT:
        try:
            sock = socket.create_connection((host, tcp_port))
            transport = TCPTransport(sock)

            return Client(process, transport, project_path)
        except ConnectionRefusedError as e:
            pass

    process.kill()
    raise Exception("Timeout connecting to socket")


def attach_stdio_client(process, project_path):
    transport = StdioTransport(process)
    if settings.log_stderr:
        attach_logger(process, process.stderr)
    return Client(process, transport, project_path)


def attach_logger(process, stream):
    threading.Thread(target=lambda: log_stream(process, stream)).start()


def log_stream(process, stream):
        """
        Reads any errors from the LSP process.
        """
        running = True
        while running:
            running = process.poll() is None

            try:
                content = process.stderr.readline()
                if not content:
                    break
                if settings.log_stderr:
                    try:
                        decoded = content.decode("UTF-8")
                    except UnicodeDecodeError:
                        decoded = content
                    log(1, "server: %s", decoded.strip())
            except IOError as err:
                log.exception("Failure reading stderr")
                return

        log(2, "LSP stderr process ended.")


class Transport(object,  metaclass=ABCMeta):
    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def start(self, on_receive, on_closed):
        pass

    @abstractmethod
    def send(self, message):
        pass


STATE_HEADERS = 0
STATE_CONTENT = 1


class TCPTransport(Transport):
    def __init__(self, socket):
        self.socket = socket

    def start(self, on_receive, on_closed):
        self.on_receive = on_receive
        self.on_closed = on_closed
        self.read_thread = threading.Thread(target=self.read_socket)
        self.read_thread.start()

    def close(self):
        self.socket = None
        self.on_closed()

    def read_socket(self):
        remaining_data = b""
        is_incomplete = False
        read_state = STATE_HEADERS
        content_length = 0
        while self.socket:
            is_incomplete = False
            try:
                received_data = self.socket.recv(4096)
            except Exception as err:
                log.exception("Failure reading from socket")
                self.close()
                break

            if not received_data:
                log(2, "no data received, closing")
                self.close()
                break

            data = remaining_data + received_data
            remaining_data = b""

            while len(data) > 0 and not is_incomplete:
                if read_state == STATE_HEADERS:
                    headers, _sep, rest = data.partition(b"\r\n\r\n")
                    if len(_sep) < 1:
                        is_incomplete = True
                        remaining_data = data
                    else:
                        for header in headers.split(b"\r\n"):
                            if header.startswith(ContentLengthHeader):
                                header_value = header[len(ContentLengthHeader):]
                                content_length = int(header_value)
                                read_state = STATE_CONTENT
                        data = rest

                if read_state == STATE_CONTENT:
                    # read content bytes
                    if len(data) >= content_length:
                        content = data[:content_length]
                        self.on_receive(content.decode("UTF-8"))
                        data = data[content_length:]
                        read_state = STATE_HEADERS
                    else:
                        is_incomplete = True
                        remaining_data = data

    def send(self, message):
        try:
            if self.socket:
                log(2, 'socket send')
                self.socket.sendall(bytes(message, 'UTF-8'))
        except Exception as err:
            log.exception("Failure writing to socket")
            self.socket = None
            self.on_closed()


class StdioTransport(Transport):
    def __init__(self, process):
        self.process = process

    def start(self, on_receive, on_closed):
        self.on_receive = on_receive
        self.on_closed = on_closed
        self.stdout_thread = threading.Thread(target=self.read_stdout)
        self.stdout_thread.start()

    def close(self):
        self.process = None
        self.on_closed()

    def read_stdout(self):
        """
        Reads JSON responses from process and dispatch them to response_handler
        """
        ContentLengthHeader = b"Content-Length: "

        running = True
        while running:
            running = self.process.poll() is None

            try:
                content_length = 0
                while self.process:
                    header = self.process.stdout.readline()
                    if header:
                        header = header.strip()
                    if not header:
                        break
                    if header.startswith(ContentLengthHeader):
                        content_length = int(header[len(ContentLengthHeader):])

                if (content_length > 0):
                    content = self.process.stdout.read(content_length)

                    self.on_receive(content.decode("UTF-8"))

            except IOError as err:
                self.close()
                log.exception("Failure reading stdout")
                break

        log(2, "LSP stdout process ended.")

    def send(self, message):
        if self.process:
            try:
                self.process.stdin.write(bytes(message, 'UTF-8'))
                self.process.stdin.flush()
            except (BrokenPipeError, OSError) as err:
                log.exception("Failure writing to stdout")
                self.close()


class Client(object):
    def __init__(self, process, transport, project_path):
        self.process = process
        self.transport = transport
        self.transport.start(self.receive_payload, self.on_transport_closed)
        self.project_path = project_path
        self.request_id = 0
        self._response_handlers = {}  # type: Dict[int, Callable]
        self._error_handlers = {}  # type: Dict[int, Callable]
        self._request_handlers = {}  # type: Dict[str, Callable]
        self._notification_handlers = {}  # type: Dict[str, Callable]
        self.capabilities = {}  # type: Dict[str, Any]
        self.exiting = False
        self._crash_handler = None  # type: Optional[Callable]

    def set_capabilities(self, capabilities):
        self.capabilities = capabilities

    def get_project_path(self):
        return self.project_path

    def has_capability(self, capability):
        return capability in self.capabilities and self.capabilities[capability] is not False

    def get_capability(self, capability):
        return self.capabilities.get(capability)

    def send_request(self, request: Request, handler: 'Callable', error_handler: 'Optional[Callable]' = None):
        self.request_id += 1
        log(2, ' --> %s', request.method)
        if handler is not None:
            self._response_handlers[self.request_id] = handler
        if error_handler is not None:
            self._error_handlers[self.request_id] = error_handler
        self.send_payload(request.to_payload(self.request_id))

    def send_notification(self, notification: Notification):
        log(2, ' --> %s', notification.method)
        self.send_payload(notification.to_payload())

    def exit(self):
        self.exiting = True
        self.send_notification(Notification.exit())

    def kill(self):
        self.process.kill()
        self.process = None

    def set_crash_handler(self, handler: 'Callable'):
        self._crash_handler = handler

    def handle_transport_failure(self):
        if self.process:
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass  # process can be terminated already
            self.process = None
            if self._crash_handler is not None:
                self._crash_handler()

    def send_payload(self, payload):
        if self.transport:
            try:
                message = format_request(payload)
                self.transport.send(message)
            except Exception as err:
                sublime.status_message("Failure sending LSP server message, exiting")
                log.exception("Failure writing payload")
                self.handle_transport_failure()

    def receive_payload(self, message):
        payload = None
        try:
            payload = json.loads(message)
            # limit = min(len(message), 200)
            # log(2, "got json: %s ...", message[0:limit])
        except IOError as err:
            log.exception("got a non-JSON payload: %s", message)
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
                log(2, "Unknown payload type: %s", payload)
        except Exception as err:
            log.exception("Error handling server payload")

    def on_transport_closed(self):
        sublime.status_message("Communication to server closed, exiting")
        # Differentiate between normal exit and server crash?
        if not self.exiting:
            self.handle_transport_failure()

    def response_handler(self, response):
        handler_id = int(response.get("id"))  # dotty sends strings back :(
        if 'result' in response and 'error' not in response:
            result = response['result']
            if settings.log_payloads:
                log(2, '     %s', str(result))
            if handler_id in self._response_handlers:
                self._response_handlers[handler_id](result)
            else:
                log(2, "No handler found for id %s", response.get("id"))
        elif 'error' in response and 'result' not in response:
            error = response['error']
            if settings.log_payloads:
                log(2, '     %s', str(error))
            if handler_id in self._error_handlers:
                self._error_handlers[handler_id](error)
            else:
                sublime.status_message(error.get('message'))
        else:
            log(2, 'invalid response payload %s', response)

    def on_request(self, request_method: str, handler: 'Callable'):
        self._request_handlers[request_method] = handler

    def on_notification(self, notification_method: str, handler: 'Callable'):
        self._notification_handlers[notification_method] = handler

    def request_handler(self, request):
        params = request.get("params")
        method = request.get("method")
        log(2, '<--  %s', method)
        if settings.log_payloads and params:
            log(2, '     %s', str(params))
        if method in self._request_handlers:
            try:
                self._request_handlers[method](params)
            except Exception as err:
                log.exception("Error handling request %s", method)
        else:
            log(2, "Unhandled request %s", method)

    def notification_handler(self, notification):
        method = notification.get("method")
        params = notification.get("params")
        if method != "window/logMessage":
            log(2, '<--  %s', method)
            if settings.log_payloads and params:
                log(2, '     %s', str(params))
        if method in self._notification_handlers:
            try:
                self._notification_handlers[method](params)
            except Exception as err:
                log.exception("Error handling notification %s", method)
        else:
            log(2, "Unhandled notification: %s", method)
