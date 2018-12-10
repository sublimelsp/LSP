from abc import ABCMeta, abstractmethod
import threading
import time
import socket
from queue import Queue
import subprocess
from .logging import exception_log, debug

try:
    from typing import Callable, Dict, Any, Optional
    assert Callable and Dict and Any and Optional and subprocess
except ImportError:
    pass


ContentLengthHeader = b"Content-Length: "
TCP_CONNECT_TIMEOUT = 5

try:
    from typing import Any, Dict, Callable
    assert Any and Dict and Callable
except ImportError:
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


STATE_HEADERS = 0
STATE_CONTENT = 1


def start_tcp_transport(port: int, host: 'Optional[str]'=None) -> 'Transport':
    start_time = time.time()
    debug('connecting to {}:{}'.format(host or "localhost", port))

    while time.time() - start_time < TCP_CONNECT_TIMEOUT:
        try:
            sock = socket.create_connection((host or "localhost", port))
            return TCPTransport(sock)
        except ConnectionRefusedError as e:
            pass

    # process.kill()
    raise Exception("Timeout connecting to socket")


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

    def send(self, message: str) -> None:
        self.send_queue.put(message)

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

    def read_stdout(self) -> None:
        """
        Reads JSON responses from process and dispatch them to response_handler
        """
        ContentLengthHeader = b"Content-Length: "

        running = True
        while running and self.process:
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
                exception_log("Failure reading stdout", err)
                break

        debug("LSP stdout process ended.")

    def send(self, message: str) -> None:
        self.send_queue.put(message)

    def write_stdin(self) -> None:
        while self.process:
            message = self.send_queue.get()
            if message is None:
                break
            else:
                try:
                    self.process.stdin.write(bytes(message, 'UTF-8'))
                    self.process.stdin.flush()
                except (BrokenPipeError, OSError) as err:
                    exception_log("Failure writing to stdout", err)
                    self.close()
