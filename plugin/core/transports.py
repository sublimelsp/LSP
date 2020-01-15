from abc import ABCMeta, abstractmethod
import threading
import time
import socket
from queue import Queue
import subprocess
from .logging import exception_log, debug

try:
    from typing import Callable, Dict, Any, Optional, IO
    assert Callable and Dict and Any and Optional and subprocess and IO
except ImportError:
    pass


ContentLengthHeader = b"Content-Length: "
ContentLengthHeader_len = len(ContentLengthHeader)
TCP_CONNECT_TIMEOUT = 5

try:
    from typing import Any, Dict, Callable
    assert Any and Dict and Callable
except ImportError:
    pass


class UnexpectedProcessExitError(Exception):
    pass


class Transport(object, metaclass=ABCMeta):
    @abstractmethod
    def __init__(self) -> None:
        pass

    @abstractmethod
    def start(self, on_receive: 'Callable[[str], None]', on_closed: 'Callable[[], None]') -> None:
        pass

    @abstractmethod
    def send(self, message: str) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


STATE_HEADERS = 0
STATE_CONTENT = 1
STATE_EOF = 2

StateStrings = {STATE_HEADERS: 'STATE_HEADERS',
                STATE_CONTENT: 'STATE_CONTENT',
                STATE_EOF:     'STATE_EOF'}


def state_to_string(state: int) -> str:
    return StateStrings.get(state, '<unknown state: {}>'.format(state))


def start_tcp_listener(tcp_port: int) -> socket.socket:
    sock = socket.socket()
    sock.bind(('', tcp_port))
    port = sock.getsockname()[1]
    sock.settimeout(TCP_CONNECT_TIMEOUT)
    debug('listening on {}:{}'.format('localhost', port))
    sock.listen(1)
    return sock


def start_tcp_transport(port: int, host: 'Optional[str]' = None) -> 'Transport':
    start_time = time.time()
    debug('connecting to {}:{}'.format(host or "localhost", port))

    while time.time() - start_time < TCP_CONNECT_TIMEOUT:
        try:
            sock = socket.create_connection((host or "localhost", port))
            return TCPTransport(sock)
        except ConnectionRefusedError:
            pass

    # process.kill()
    raise Exception("Timeout connecting to socket")


def build_message(content: str) -> str:
    content_length = len(content)
    result = "Content-Length: {}\r\n\r\n{}".format(content_length, content)
    return result


class TCPTransport(Transport):
    def __init__(self, socket: 'Any') -> None:
        self.socket = socket  # type: 'Optional[Any]'
        self.send_queue = Queue()  # type: Queue[Optional[str]]

    def start(self, on_receive: 'Callable[[str], None]', on_closed: 'Callable[[], None]') -> None:
        self.on_receive = on_receive
        self.on_closed = on_closed
        self.read_thread = threading.Thread(target=self.read_socket)
        self.read_thread.start()
        self.write_thread = threading.Thread(target=self.write_socket)
        self.write_thread.start()

    def close(self) -> None:
        self.send_queue.put(None)  # kill the write thread as it's blocked on send_queue
        self.socket = None
        self.on_closed()

    def read_socket(self) -> None:
        remaining_data = b""
        is_incomplete = False
        read_state = STATE_HEADERS
        content_length = 0
        while self.socket:
            is_incomplete = False
            try:
                received_data = self.socket.recv(4096)
            except Exception as err:
                exception_log("Failure reading from socket", err)
                self.close()
                break

            if not received_data:
                debug("no data received, closing")
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
                                header_value = header[ContentLengthHeader_len:]
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

    def send(self, content: str) -> None:
        self.send_queue.put(build_message(content))

    def write_socket(self) -> None:
        while self.socket:
            message = self.send_queue.get()
            if message is None:
                break
            else:
                try:
                    self.socket.sendall(bytes(message, 'UTF-8'))
                except Exception as err:
                    exception_log("Failure writing to socket", err)
                    self.close()


class StdioTransport(Transport):
    def __init__(self, process: 'subprocess.Popen') -> None:
        self.process = process  # type: Optional[subprocess.Popen]
        self.send_queue = Queue()  # type: Queue[Optional[str]]

    def start(self, on_receive: 'Callable[[str], None]', on_closed: 'Callable[[], None]') -> None:
        self.on_receive = on_receive
        self.on_closed = on_closed
        self.write_thread = threading.Thread(target=self.write_stdin)
        self.write_thread.start()
        self.read_thread = threading.Thread(target=self.read_stdout)
        self.read_thread.start()

    def close(self) -> None:
        self.process = None
        self.send_queue.put(None)  # kill the write thread as it's blocked on send_queue
        self.on_closed()

    def _checked_stdout(self) -> 'IO[Any]':
        if self.process:
            return self.process.stdout
        else:
            raise UnexpectedProcessExitError()

    def read_stdout(self) -> None:
        """
        Reads JSON responses from process and dispatch them to response_handler
        """
        running = True
        pid = self.process.pid if self.process else "???"
        state = STATE_HEADERS
        content_length = 0
        while running and self.process and state != STATE_EOF:
            running = self.process.poll() is None
            try:
                # debug("read_stdout: state = {}".format(state_to_string(state)))
                if state == STATE_HEADERS:
                    header = self._checked_stdout().readline()
                    # debug('read_stdout reads: {}'.format(header))
                    if not header:
                        # Truly, this is the EOF on the stream
                        state = STATE_EOF
                        break

                    header = header.strip()
                    if not header:
                        # Not EOF, blank line -> content follows
                        state = STATE_CONTENT
                    elif header.startswith(ContentLengthHeader):
                        content_length = int(header[ContentLengthHeader_len:])
                elif state == STATE_CONTENT:
                    if content_length > 0:
                        content = self._checked_stdout().read(content_length)
                        self.on_receive(content.decode("UTF-8"))
                        # debug("read_stdout: read and received {} byte message".format(content_length))
                        content_length = 0
                    state = STATE_HEADERS

            except IOError as err:
                self.close()
                exception_log("Failure reading stdout", err)
                state = STATE_EOF
                break
            except UnexpectedProcessExitError:
                self.close()
                debug("process became None")
                state = STATE_EOF
                break
        debug("process {} stdout ended {}".format(pid, "(still alive)" if self.process else "(terminated)"))
        if self.process:
            # We use the stdout thread to block and wait on the exiting process, or zombie processes may be the result.
            returncode = self.process.wait()
            debug("process {} exited with code {}".format(pid, returncode))
        self.send_queue.put(None)

    def send(self, content: str) -> None:
        self.send_queue.put(build_message(content))

    def write_stdin(self) -> None:
        while self.process:
            message = self.send_queue.get()
            if message is None:
                break
            else:
                try:
                    msgbytes = bytes(message, 'UTF-8')
                    try:
                        self.process.stdin.write(msgbytes)
                    except AttributeError:
                        return
                    self.process.stdin.flush()
                except (BrokenPipeError, OSError) as err:
                    exception_log("Failure writing to stdout", err)
                    self.close()
