from .logging import exception_log, debug
from .types import TCP_CONNECT_TIMEOUT
from .types import TransportConfig
from .typing import Dict, Any, Optional, IO, Protocol, Generic, List, Callable, Tuple, TypeVar, Union
from contextlib import closing
from functools import partial
from queue import Queue
import http.client
import json
import multiprocessing.connection
import os
import shutil
import socket
import sublime
import subprocess
import threading
import time
import weakref


T = TypeVar('T')
T_contra = TypeVar('T_contra', contravariant=True)


class StopLoopError(Exception):
    pass


class Transport(Generic[T]):

    def send(self, payload: T) -> None:
        raise NotImplementedError()

    def close(self) -> None:
        raise NotImplementedError()


class TransportCallbacks(Protocol[T_contra]):

    def on_transport_close(self, exit_code: int, exception: Optional[Exception]) -> None:
        ...

    def on_payload(self, payload: T_contra) -> None:
        ...

    def on_stderr_message(self, message: str) -> None:
        ...


class AbstractProcessor(Generic[T]):

    def write_data(self, data: T) -> None:
        raise NotImplementedError()

    def read_data(self) -> Optional[T]:
        raise NotImplementedError()


def encode_payload(data: Dict[str, Any]) -> bytes:
    return json.dumps(
        data,
        ensure_ascii=False,
        check_circular=False,
        separators=(',', ':')
    ).encode('utf-8')


def decode_payload(message: bytes) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(message.decode('utf-8'))
    except Exception as ex:
        exception_log("JSON decode error", ex)
        return None


class StandardProcessor(AbstractProcessor[Dict[str, Any]]):

    def __init__(self, reader: IO[bytes], writer: IO[bytes]):
        self._reader = reader
        self._writer = writer

    def write_data(self, data: Dict[str, Any]) -> None:
        body = encode_payload(data)
        self._writer.writelines(("Content-Length: {}\r\n\r\n".format(len(body)).encode('ascii'), body))
        self._writer.flush()

    def read_data(self) -> Optional[Dict[str, Any]]:
        headers = http.client.parse_headers(self._reader)  # type: ignore
        try:
            body = self._reader.read(int(headers.get("Content-Length")))
        except TypeError:
            # Expected error on process stopping. Stop the read loop.
            raise StopLoopError()
        return decode_payload(body)


class NodeIpcProcessor(AbstractProcessor[Dict[str, Any]]):
    _buf = bytearray()
    _lines = 0

    def __init__(self, conn: multiprocessing.connection._ConnectionBase):
        self._conn = conn

    def write_data(self, data: Dict[str, Any]) -> None:
        body = encode_payload(data) + b"\n"
        while len(body):
            n = self._conn._write(self._conn.fileno(), body)  # type: ignore
            body = body[n:]

    def read_data(self) -> Optional[Dict[str, Any]]:
        while self._lines == 0:
            chunk = self._conn._read(self._conn.fileno(), 65536)  # type: ignore
            if len(chunk) == 0:
                # EOF reached: https://docs.python.org/3/library/os.html#os.read
                raise StopLoopError()

            self._buf += chunk
            self._lines += chunk.count(b'\n')

        self._lines -= 1
        message, _, self._buf = self._buf.partition(b'\n')
        return decode_payload(message)


class ProcessTransport(Transport[T]):

    def __init__(self,
                 name: str,
                 process: subprocess.Popen,
                 socket: Optional[socket.socket],
                 stderr: Optional[IO[bytes]],
                 processor: AbstractProcessor[T],
                 callback_object: TransportCallbacks[T]) -> None:
        self._closed = False
        self._process = process
        self._socket = socket
        self._stderr = stderr
        self._processor = processor
        self._reader_thread = threading.Thread(target=self._read_loop, name='{}-reader'.format(name))
        self._writer_thread = threading.Thread(target=self._write_loop, name='{}-writer'.format(name))
        self._stderr_thread = threading.Thread(target=self._stderr_loop, name='{}-stderr'.format(name))
        self._callback_object = weakref.ref(callback_object)
        self._send_queue = Queue(0)  # type: Queue[Union[T, None]]
        self._reader_thread.start()
        self._writer_thread.start()
        self._stderr_thread.start()

    def send(self, payload: T) -> None:
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
            while True:
                payload = self._processor.read_data()
                if payload is None:
                    continue

                def invoke(p: T) -> None:
                    if self._closed:
                        return
                    callback_object = self._callback_object()
                    if callback_object:
                        callback_object.on_payload(p)

                sublime.set_timeout_async(partial(invoke, payload))
        except (AttributeError, BrokenPipeError, StopLoopError):
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
        if self._process.poll() is None:
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

        def invoke() -> None:
            callback_object = self._callback_object()
            if callback_object:
                callback_object.on_transport_close(exit_code, exception)

        sublime.set_timeout_async(invoke)
        self.close()

    def _write_loop(self) -> None:
        exception = None  # type: Optional[Exception]
        try:
            while True:
                d = self._send_queue.get()
                if d is None:
                    break
                self._processor.write_data(d)
        except (BrokenPipeError, AttributeError):
            pass
        except Exception as ex:
            exception = ex
        self._end(exception)

    def _stderr_loop(self) -> None:
        try:
            while self._stderr:
                if self._closed:
                    # None message already posted, just return
                    return
                message = self._stderr.readline().decode('utf-8', 'replace')
                if message == '':
                    continue
                callback_object = self._callback_object()
                if callback_object:
                    callback_object.on_stderr_message(message.rstrip())
                else:
                    break
        except (BrokenPipeError, AttributeError):
            pass
        except Exception as ex:
            exception_log('unexpected exception type in stderr loop', ex)
        self._send_queue.put_nowait(None)


def create_transport(config: TransportConfig, cwd: Optional[str],
                     callback_object: TransportCallbacks) -> Transport[Dict[str, Any]]:
    stderr = subprocess.PIPE
    pass_fds = ()  # type: Union[Tuple[()], Tuple[int]]
    if config.tcp_port is not None:
        assert config.tcp_port is not None
        if config.tcp_port < 0:
            stdout = subprocess.PIPE
        else:
            stdout = subprocess.DEVNULL
        stdin = subprocess.DEVNULL
    elif not config.node_ipc:
        stdout = subprocess.PIPE
        stdin = subprocess.PIPE
    else:
        stdout = subprocess.PIPE
        stdin = subprocess.DEVNULL
        stderr = subprocess.STDOUT
        pass_fds = (config.node_ipc.child_conn.fileno(),)

    startupinfo = _fixup_startup_args(config.command)
    sock = None  # type: Optional[socket.socket]
    process = None  # type: Optional[subprocess.Popen]

    def start_subprocess() -> subprocess.Popen:
        return _start_subprocess(config.command, stdin, stdout, stderr, startupinfo, config.env, cwd, pass_fds)

    if config.listener_socket:
        assert isinstance(config.tcp_port, int) and config.tcp_port > 0
        process, sock, reader, writer = _await_tcp_connection(
            config.name,
            config.tcp_port,
            config.listener_socket,
            start_subprocess
        )
        processor = StandardProcessor(reader, writer)  # type: AbstractProcessor
    else:
        process = start_subprocess()
        if config.tcp_port:
            sock = _connect_tcp(config.tcp_port)
            if sock is None:
                raise RuntimeError("Failed to connect on port {}".format(config.tcp_port))
            reader = writer = sock.makefile('rwb')
            processor = StandardProcessor(reader, writer)
        elif not config.node_ipc:
            if not process.stdout or not process.stdin:
                raise RuntimeError(
                    'Failed initializing transport: reader: {}, writer: {}'
                    .format(process.stdout, process.stdin)
                )
            processor = StandardProcessor(process.stdout, process.stdin)
        else:
            processor = NodeIpcProcessor(config.node_ipc.parent_conn)

    stderr_reader = process.stdout if config.node_ipc else process.stderr
    return ProcessTransport(config.name, process, sock, stderr_reader, processor, callback_object)


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


def _fixup_startup_args(args: List[str]) -> Any:
    startupinfo = None
    if sublime.platform() == "windows":
        startupinfo = subprocess.STARTUPINFO()  # type: ignore
        startupinfo.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW  # type: ignore
        executable_arg = args[0]
        _, ext = os.path.splitext(executable_arg)
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
    return startupinfo


def _start_subprocess(
    args: List[str],
    stdin: int,
    stdout: int,
    stderr: int,
    startupinfo: Any,
    env: Dict[str, str],
    cwd: Optional[str],
    pass_fds: Union[Tuple[()], Tuple[int]]
) -> subprocess.Popen:
    debug("starting {} in {}".format(args, cwd if cwd else os.getcwd()))
    process = subprocess.Popen(
        args=args,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        startupinfo=startupinfo,
        env=env,
        cwd=cwd,
        pass_fds=pass_fds)
    _subprocesses.add(process)
    return process


class _SubprocessData:
    def __init__(self) -> None:
        self.process = None  # type: Optional[subprocess.Popen]


def _await_tcp_connection(
    name: str,
    tcp_port: int,
    listener_socket: socket.socket,
    subprocess_starter: Callable[[], subprocess.Popen]
) -> Tuple[subprocess.Popen, socket.socket, IO[bytes], IO[bytes]]:

    # After we have accepted one client connection, we can close the listener socket.
    with closing(listener_socket):

        # We need to be able to start the process while also awaiting a client connection.
        def start_in_background(d: _SubprocessData) -> None:
            # Sleep for one second, because the listener socket needs to be in the "accept" state before starting the
            # subprocess. This is hacky, and will get better when we can use asyncio.
            time.sleep(1)
            process = subprocess_starter()
            d.process = process

        data = _SubprocessData()
        thread = threading.Thread(target=lambda: start_in_background(data))
        thread.start()
        # Await one client connection (blocking!)
        sock, _ = listener_socket.accept()
        thread.join()
        reader = writer = sock.makefile('rwb')
        assert data.process
        return data.process, sock, reader, writer


def _connect_tcp(port: int) -> Optional[socket.socket]:
    start_time = time.time()
    while time.time() - start_time < TCP_CONNECT_TIMEOUT:
        try:
            return socket.create_connection(('localhost', port))
        except ConnectionRefusedError:
            pass
    return None
