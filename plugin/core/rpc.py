import json
import sublime
import threading

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass

from .settings import settings
from .logging import debug, exception_log, server_log
from .protocol import Request, Notification


def format_request(payload: 'Dict[str, Any]'):
    """Converts the request into json and adds the Content-Length header"""
    content = json.dumps(payload, sort_keys=False)
    content_length = len(content)
    result = "Content-Length: {}\r\n\r\n{}".format(content_length, content)
    return result


class Client(object):
    def __init__(self, process, project_path):
        self.process = process
        self.stdout_thread = threading.Thread(target=self.read_stdout)
        self.stdout_thread.start()
        self.stderr_thread = threading.Thread(target=self.read_stderr)
        self.stderr_thread.start()
        self.project_path = project_path
        self.request_id = 0
        self._response_handlers = {}  # type: Dict[int, Callable]
        self._request_handlers = {}  # type: Dict[str, Callable]
        self._notification_handlers = {}  # type: Dict[str, Callable]
        self.capabilities = {}  # type: Dict[str, Any]
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._blocking_request_id = -1
        self._scratch_response = None

    def set_capabilities(self, capabilities):
        self.capabilities = capabilities

    def get_project_path(self):
        return self.project_path

    def has_capability(self, capability):
        return capability in self.capabilities

    def get_capability(self, capability):
        return self.capabilities.get(capability)

    def send_request(self, request: Request, handler: 'Callable', blocking=False):
        self.request_id += 1
        debug('request', self.request_id, ':', request.method, ', blocking =', blocking)
        if blocking:
            with self._condition:
                try:
                    self._blocking_request_id = self.request_id
                    self.send_payload(request.to_payload(self.request_id))
                    if not self._condition.wait_for(lambda: self._scratch_response is not None, 6):
                        debug("blocking request timed out")
                    elif self._scratch_response == "ERROR":
                        pass  # Errors are handled in the stdout thread.
                    elif self._scratch_response == "EMPTY":
                        handler(None)
                    else:
                        handler(self._scratch_response)
                except Exception as e:
                    raise e
                finally:
                    self._blocking_request_id = -1
                    self._scratch_response = None
        else:
            if handler is not None:
                self._response_handlers[self.request_id] = handler
            self.send_payload(request.to_payload(self.request_id))

    def send_notification(self, notification: Notification):
        debug('notify: ' + notification.method)
        self.send_payload(notification.to_payload())

    def kill(self):
        self.process.kill()

    def send_payload(self, payload):
        try:
            message = format_request(payload)
            self.process.stdin.write(bytes(message, 'UTF-8'))
            self.process.stdin.flush()
        except BrokenPipeError as err:
            sublime.status_message("Failure sending LSP server message, exiting")
            exception_log("Failure writing payload", err)
            self.process.terminate()
            self.process = None

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
                while True:
                    header = self.process.stdout.readline()
                    if header:
                        header = header.strip()
                    if not header:
                        break
                    if header.startswith(ContentLengthHeader):
                        content_length = int(header[len(ContentLengthHeader):])

                if (content_length > 0):
                    content = self.process.stdout.read(content_length).decode(
                        "UTF-8")

                    payload = None
                    try:
                        payload = json.loads(content)
                        limit = min(len(content), 200)
                        if payload.get("method") != "window/logMessage":
                            debug("got json: ", content[0:limit], "...")
                    except IOError as err:
                        exception_log("got a non-JSON payload: " + content, err)
                        continue

                    try:
                        if "error" in payload:
                            error = payload['error']
                            debug("Got error from server: ", error)
                            sublime.status_message(error.get('message'))
                            if self._blocking_request_id >= 0:
                                self._scratch_response = "ERROR"
                                with self._condition:
                                    self._condition.notify()
                        elif "method" in payload:
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

            except IOError as err:
                sublime.status_message("Failure reading LSP server response, exiting")
                exception_log("Failure reading stdout", err)
                self.process.terminate()
                self.process = None
                return

        debug("LSP stdout process ended.")

    def read_stderr(self):
        """
        Reads any errors from the LSP process.
        """
        running = True
        while running:
            running = self.process.poll() is None

            try:
                content = self.process.stderr.readline()
                if not content:
                    break
                if settings.log_stderr:
                    server_log("(stderr): ", content.strip())
            except IOError as err:
                exception_log("Failure reading stderr", err)
                return

        debug("LSP stderr process ended.")

    def response_handler(self, response):
        handler_id = int(response.get("id"))  # dotty sends strings back :(
        if self._blocking_request_id == handler_id:
            self._scratch_response = response.get("result", "EMPTY")
            with self._condition:
                self._condition.notify()
        else:
            result = response.get('result', None)
            if (self._response_handlers[handler_id]):
                self._response_handlers[handler_id](result)
            else:
                debug("No handler found for id" + response.get("id"))

    def on_request(self, request_method: str, handler: 'Callable'):
        self._request_handlers[request_method] = handler

    def on_notification(self, notification_method: str, handler: 'Callable'):
        self._notification_handlers[notification_method] = handler

    def request_handler(self, request):
        method = request.get("method")
        if method in self._request_handlers:
            try:
                self._request_handlers[method](request.get("params"))
            except Exception as err:
                exception_log("Error handling request " + method, err)
        else:
            debug("Unhandled request", method)

    def notification_handler(self, response):
        method = response.get("method")
        if method in self._notification_handlers:
            try:
                self._notification_handlers[method](response.get("params"))
            except Exception as err:
                exception_log("Error handling request " + method, err)
        else:
            debug("Unhandled notification:", method)
