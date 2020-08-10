from .logging import exception_log, debug
from .types import ClientConfig
from .typing import Dict, Any, Optional, IO, Protocol
from abc import ABCMeta, abstractmethod
from contextlib import closing
from queue import Queue
import json
import os
import shutil
import socket
import sublime
import subprocess
import threading
import time
import weakref


TCP_CONNECT_TIMEOUT = 5


class Transport(metaclass=ABCMeta):

    @abstractmethod
    def send(self, payload: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


class TransportCallbacks(Protocol):

    def on_transport_close(self, exit_code: int, exception: Optional[Exception]) -> None:
        ...

    def on_payload(self, payload: Dict[str, Any]) -> None:
        ...

    def on_stderr_message(self, message: str) -> None:
        ...


class JsonRpcTransport(Transport):

    def __init__(self, name: str, process: subprocess.Popen, socket: Optional[socket.socket], reader: IO[bytes],
                 writer: IO[bytes], stderr: Optional[IO[bytes]], callback_object: TransportCallbacks) -> None:
        self._process = process
        self._socket = socket
        self._reader = reader
        self._writer = writer
        self._stderr = stderr
        self._reader_thread = threading.Thread(target=self._read_loop, name='{}-reader'.format(name))
        self._writer_thread = threading.Thread(target=self._write_loop, name='{}-writer'.format(name))
        self._stderr_thread = threading.Thread(target=self._stderr_loop, name='{}-stderr'.format(name))
        self._callback_object = weakref.ref(callback_object)
        self._send_queue = Queue(0)  # type: Queue[Optional[Dict[str, Any]]]
        self._reader_thread.start()
        self._writer_thread.start()
        self._stderr_thread.start()
        self._closed = False

    def send(self, payload: Dict[str, Any]) -> None:
        self._send_queue.put_nowait(payload)

    def close(self) -> None:
        if not self._closed:
            self._send_queue.put_nowait(None)
            if self._socket:
                self._socket.close()
            self._closed = True

    def _join_thread(self, t: threading.Thread) -> None:
        if t.ident == threading.current_thread().ident:
            return
        try:
            t.join(2)
        except TimeoutError as ex:
            exception_log("failed to join {} thread".format(t.name), ex)

    def __del__(self) -> None:
        self.close()
        self._join_thread(self._writer_thread)
        self._join_thread(self._reader_thread)
        self._join_thread(self._stderr_thread)

    def _read_loop(self) -> None:
        try:
            while self._reader:
                line = self._reader.readline()
                if not line:
                    break
                try:
                    num_bytes = _content_length(line)
                except ValueError:
                    continue
                if num_bytes is None:
                    continue
                while line and line.strip():
                    line = self._reader.readline()
                if not line:
                    continue
                body = self._reader.read(num_bytes)
                callback_object = self._callback_object()
                if callback_object:
                    try:
                        callback_object.on_payload(_decode(body))
                    except Exception as ex:
                        exception_log("Error handling payload", ex)
                else:
                    break
        except (AttributeError, BrokenPipeError):
            pass
        except Exception as ex:
            exception_log("Unexpected exception", ex)
        self._send_queue.put_nowait(None)

    def _end(self, exception: Optional[Exception]) -> None:
        exit_code = 0
        if not exception:
            try:
                # Allow the process to stop itself.
                exit_code = self._process.wait(1)
            except (AttributeError, ProcessLookupError, subprocess.TimeoutExpired):
                pass
        if self._process:
            try:
                # The process didn't stop itself. Terminate!
                self._process.kill()
                # still wait for the process to die, or zombie processes might be the result
                # Ignore the exit code in this case, it's going to be something non-zero because we sent SIGKILL.
                self._process.wait()
            except (AttributeError, ProcessLookupError):
                pass
            except Exception as ex:
                exception = ex  # TODO: Old captured exception is overwritten
        callback_object = self._callback_object()
        if callback_object:
            callback_object.on_transport_close(exit_code, exception)

    def _write_loop(self) -> None:
        exception = None  # type: Optional[Exception]
        try:
            while self._writer:
                d = self._send_queue.get()
                if d is None:
                    break
                body = _encode(d)
                self._writer.writelines(("Content-Length: {}\r\n\r\n".format(len(body)).encode('ascii'), body))
                self._writer.flush()
        except (BrokenPipeError, AttributeError):
            pass
        except Exception as ex:
            exception = ex
        self._end(exception)

    def _stderr_loop(self) -> None:
        try:
            while self._stderr:
                message = self._stderr.readline().decode('utf-8', 'replace').rstrip()
                if not message:
                    break
                callback_object = self._callback_object()
                if callback_object:
                    callback_object.on_stderr_message(message)
                else:
                    break
        except (BrokenPipeError, AttributeError):
            pass
        except Exception as ex:
            exception_log('unexpected exception type in stderr loop', ex)
        self._send_queue.put_nowait(None)


def create_transport(config: ClientConfig, cwd: Optional[str], window: sublime.Window,
                     callback_object: TransportCallbacks, variables: Dict[str, str]) -> JsonRpcTransport:
    tcp_port = None  # type: Optional[int]
    if config.tcp_port is not None:
        tcp_port = _find_free_port() if config.tcp_port == 0 else config.tcp_port
    if tcp_port is not None:
        variables["port"] = str(tcp_port)
    args = sublime.expand_variables(config.binary_args, variables)
    args = [os.path.expanduser(arg) for arg in args]
    if tcp_port is not None:
        # DEPRECATED -- replace {port} with $port or ${port} in your client config
        args = [a.replace('{port}', str(tcp_port)) for a in args]
    env = os.environ.copy()
    for var, value in config.env.items():
        env[var] = sublime.expand_variables(value, variables)
    if tcp_port is not None:
        stdout = subprocess.DEVNULL
        stdin = subprocess.DEVNULL
    else:
        stdout = subprocess.PIPE
        stdin = subprocess.PIPE
    if sublime.platform() == "windows":
        startupinfo = subprocess.STARTUPINFO()  # type: ignore
        startupinfo.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW  # type: ignore
        executable_arg = args[0]
        fname, ext = os.path.splitext(executable_arg)
        if len(ext) < 1:
            path_to_executable = shutil.which(executable_arg)
            # what extensions should we append so CreateProcess can find it?
            # node has .cmd
            # dart has .bat
            # python has .exe wrappers - not needed
            for extension in ['.cmd', '.bat']:
                if path_to_executable and path_to_executable.lower().endswith(extension):
                    args[0] = executable_arg + extension
                    break
    else:
        startupinfo = None
    debug("starting {} in {}".format(args, cwd if cwd else os.getcwd()))
    process = subprocess.Popen(
        args=args,
        stdin=stdin,
        stdout=stdout,
        stderr=subprocess.PIPE,
        startupinfo=startupinfo,
        env=env,
        cwd=cwd)
    _subprocesses.add(process)
    sock = None  # type: Optional[socket.socket]
    if tcp_port:
        sock = _connect_tcp(tcp_port)
        if sock is None:
            raise RuntimeError("Failed to connect on port {}".format(config.tcp_port))
        reader = sock.makefile('rwb')  # type: IO[bytes]
        writer = reader
    else:
        reader = process.stdout  # type: ignore
        writer = process.stdin  # type: ignore
    return JsonRpcTransport(config.name, process, sock, reader, writer, process.stderr, callback_object)


_subprocesses = weakref.WeakSet()  # type: weakref.WeakSet[subprocess.Popen]


def kill_all_subprocesses() -> None:
    global _subprocesses
    subprocesses = list(_subprocesses)
    for p in subprocesses:
        try:
            p.kill()
        except Exception:
            pass
    for p in subprocesses:
        try:
            p.wait()
        except Exception:
            pass


def _connect_tcp(port: int) -> Optional[socket.socket]:
    start_time = time.time()
    while time.time() - start_time < TCP_CONNECT_TIMEOUT:
        try:
            return socket.create_connection(('localhost', port))
        except ConnectionRefusedError:
            pass
    return None


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def _encode(d: Dict[str, Any]) -> bytes:
    return json.dumps(d, sort_keys=False, check_circular=False, separators=(',', ':')).encode('utf-8')


def _decode(message: bytes) -> Dict[str, Any]:
    return json.loads(message.decode('utf-8'))


def _content_length(line: bytes) -> Optional[int]:
    if line.startswith(b'Content-Length: '):
        _, value = line.split(b'Content-Length: ')
        value = value.strip()
        try:
            return int(value)
        except ValueError as ex:
            raise ValueError("Invalid Content-Length header: {}".format(value.decode('ascii'))) from ex
    return None
