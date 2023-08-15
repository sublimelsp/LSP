from .logging import exception_log, debug
from .types import TCP_CONNECT_TIMEOUT
from .types import TransportConfig
from .typing import Dict, Any, Optional, IO, Protocol, Generic, List, Callable, Tuple, TypeVar, Union
from contextlib import closing
from functools import partial
from queue import Queue
import http
import json
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

    def write_data(self, writer: IO[bytes], data: T) -> None:
        raise NotImplementedError()

    def read_data(self, reader: IO[bytes]) -> Optional[T]:
        raise NotImplementedError()


class JsonRpcProcessor(AbstractProcessor[Dict[str, Any]]):

    def write_data(self, writer: IO[bytes], data: Dict[str, Any]) -> None:
        body = self._encode(data)
        writer.writelines(("Content-Length: {}\r\n\r\n".format(len(body)).encode('ascii'), body))

    def read_data(self, reader: IO[bytes]) -> Optional[Dict[str, Any]]:
        headers = http.client.parse_headers(reader)  # type: ignore
        try:
            body = reader.read(int(headers.get("Content-Length")))
        except TypeError:
            if str(headers) == '\n':
                # Expected on process stopping. Gracefully stop the transport.
                raise StopLoopError()
            else:
                # Propagate server's output to the UI.
                raise Exception("Unexpected payload in server's stdout:\n\n{}".format(headers))
        try:
            return self._decode(body)
        except Exception as ex:
            raise Exception("JSON decode error: {}".format(ex))

    @staticmethod
    def _encode(data: Dict[str, Any]) -> bytes:
        return json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=False,
            check_circular=False,
            separators=(',', ':')
        ).encode('utf-8')

    @staticmethod
    def _decode(message: bytes) -> Dict[str, Any]:
        return json.loads(message.decode('utf-8'))


class ProcessTransport(Transport[T]):

    def __init__(self, name: str, process: Optional[subprocess.Popen], socket: Optional[socket.socket],
                 reader: IO[bytes], writer: IO[bytes], stderr: Optional[IO[bytes]],
                 processor: AbstractProcessor[T], callback_object: TransportCallbacks[T]) -> None:
        self._closed = False
        self._process = process
        self._socket = socket
        self._reader = reader
        self._writer = writer
        self._stderr = stderr
        self._processor = processor
        self._reader_thread = threading.Thread(target=self._read_loop, name='{}-reader'.format(name))
        self._writer_thread = threading.Thread(target=self._write_loop, name='{}-writer'.format(name))
        self._callback_object = weakref.ref(callback_object)
        self._send_queue = Queue(0)  # type: Queue[Union[T, None]]
        self._reader_thread.start()
        self._writer_thread.start()
        if stderr:
            self._stderr_thread = threading.Thread(target=self._stderr_loop, name='{}-stderr'.format(name))
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
        if self._stderr_thread:
            self._join_thread(self._stderr_thread)

    def _read_loop(self) -> None:
        exception = None
        try:
            while self._reader:
                payload = self._processor.read_data(self._reader)
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
            exception = ex
        if exception:
            self._end(exception)
        else:
            self._send_queue.put_nowait(None)

    def _end(self, exception: Optional[Exception]) -> None:
        exit_code = 0
        if self._process:
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
            while self._writer:
                d = self._send_queue.get()
                if d is None:
                    break
                self._processor.write_data(self._writer, d)
                self._writer.flush()
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


# Can be a singleton since it doesn't hold any state.
json_rpc_processor = JsonRpcProcessor()


def create_transport(config: TransportConfig, cwd: Optional[str],
                     callback_object: TransportCallbacks) -> Transport[Dict[str, Any]]:
    if config.tcp_port is not None:
        assert config.tcp_port is not None
        if config.tcp_port < 0:
            stdout = subprocess.PIPE
        else:
            stdout = subprocess.DEVNULL
        stdin = subprocess.DEVNULL
    else:
        stdout = subprocess.PIPE
        stdin = subprocess.PIPE
    startupinfo = _fixup_startup_args(config.command)
    sock = None  # type: Optional[socket.socket]
    process = None  # type: Optional[subprocess.Popen]

    def start_subprocess() -> subprocess.Popen:
        return _start_subprocess(config.command, stdin, stdout, subprocess.PIPE, startupinfo, config.env, cwd)

    if config.listener_socket:
        assert isinstance(config.tcp_port, int) and config.tcp_port > 0
        process, sock, reader, writer = _await_tcp_connection(
            config.name, config.tcp_port, config.listener_socket, start_subprocess)
    else:
        if config.command:
            process = start_subprocess()
        elif not config.tcp_port:
            raise RuntimeError("Failed to provide command or tcp_port, at least one of them has to be configured")
        if config.tcp_port:
            sock = _connect_tcp(config.tcp_port)
            if sock is None:
                raise RuntimeError("Failed to connect on port {}".format(config.tcp_port))
            reader = sock.makefile('rwb')  # type: ignore
            writer = reader
        else:
            reader = process.stdout  # type: ignore
            writer = process.stdin  # type: ignore
    if not reader or not writer:
        raise RuntimeError('Failed initializing transport: reader: {}, writer: {}'.format(reader, writer))
    stderr = process.stderr if process else None
    return ProcessTransport(
        config.name, process, sock, reader, writer, stderr, json_rpc_processor, callback_object)  # type: ignore


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
    cwd: Optional[str]
) -> subprocess.Popen:
    debug("starting {} in {}".format(args, cwd if cwd else os.getcwd()))
    process = subprocess.Popen(
        args=args,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        startupinfo=startupinfo,
        env=env,
        cwd=cwd)
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
        reader = sock.makefile('rwb')  # type: ignore
        writer = reader
        assert data.process
        return data.process, sock, reader, writer  # type: ignore


def _connect_tcp(port: int) -> Optional[socket.socket]:
    start_time = time.time()
    while time.time() - start_time < TCP_CONNECT_TIMEOUT:
        try:
            return socket.create_connection(('localhost', port))
        except ConnectionRefusedError:
            pass
    return None
