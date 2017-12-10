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
        self._error_handlers = {}  # type: Dict[int, Callable]
        self._request_handlers = {}  # type: Dict[str, Callable]
        self._notification_handlers = {}  # type: Dict[str, Callable]
        self.capabilities = {}  # type: Dict[str, Any]

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
        debug(' --> ' + request.method)
        if handler is not None:
            self._response_handlers[self.request_id] = handler
        if error_handler is not None:
            self._error_handlers[self.request_id] = error_handler
        self.send_payload(request.to_payload(self.request_id))

    def send_notification(self, notification: Notification):
        debug(' --> ' + notification.method)
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
                        # limit = min(len(content), 200)
                        # debug("got json: ", content[0:limit], "...")
                    except IOError as err:
                        exception_log("got a non-JSON payload: " + content, err)
                        continue

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
                    try:
                        decoded = content.decode("UTF-8")
                    except UnicodeDecodeError:
                        decoded = content
                    server_log(decoded.strip())
            except IOError as err:
                exception_log("Failure reading stderr", err)
                return

        debug("LSP stderr process ended.")

    def response_handler(self, response):
        handler_id = int(response.get("id"))  # dotty sends strings back :(
        if 'result' in response and 'error' not in response:
            result = response['result']
            if settings.log_payloads:
                debug('     ' + str(result))

            if handler_id in self._response_handlers:
                self._response_handlers[handler_id](result)
            else:
                debug("No handler found for id" + response.get("id"))
        elif 'error' in response and 'result' not in response:
            error = response.get('result')
            if settings.log_payloads:
                debug('     ' + str(error))
            if handler_id in self._error_handlers:
                self._error_handlers[handler_id](error)
            else:
                sublime.status_message(error.get('message'))
        else:
            debug('invalid response payload', response)

    def on_request(self, request_method: str, handler: 'Callable'):
        self._request_handlers[request_method] = handler

    def on_notification(self, notification_method: str, handler: 'Callable'):
        self._notification_handlers[notification_method] = handler

    def request_handler(self, request):
        params = request.get("params")
        method = request.get("method")
        debug('<--  ' + method)
        if settings.log_payloads and params:
            debug('     ' + str(params))
        if method in self._request_handlers:
            try:
                self._request_handlers[method](params)
            except Exception as err:
                exception_log("Error handling request " + method, err)
        else:
            debug("Unhandled request", method)

    def notification_handler(self, notification):
        method = notification.get("method")
        params = notification.get("params")
        if method != "window/logMessage":
            debug('<--  ' + method)
            if settings.log_payloads and params:
                debug('     ' + str(params))
        if method in self._notification_handlers:
            try:
                self._notification_handlers[method](params)
            except Exception as err:
                exception_log("Error handling notification " + method, err)
        else:
            debug("Unhandled notification:", method)
