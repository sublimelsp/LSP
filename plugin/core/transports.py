from __future__ import annotations

from .constants import ST_PLATFORM
from .logging import debug
from .logging import exception_log
from .promise import PackagedTask
from .promise import Promise
from .protocol import JSONRPCMessage
from abc import ABC
from abc import abstractmethod
from contextlib import closing
from functools import partial
from io import BufferedIOBase
from queue import Queue
from typing import Any
from typing import Callable
from typing import final
from typing import IO
from typing_extensions import override
import contextlib
import http.client
import json
import os
import shutil
import socket
import sublime
import subprocess
import threading
import time
import weakref

try:
    import orjson
except ImportError:
    orjson = None

TCP_CONNECT_TIMEOUT = 5  # seconds


class StopLoopError(Exception):
    pass


# --- Transport Configs ------------------------------------------------------------------------------------------------


class TransportConfig(ABC):
    """The object that does the actual RPC communication."""

    @staticmethod
    def resolve_launch_config(
        command: list[str],
        env: dict[str, str] | None,
        variables: dict[str, str],
    ) -> LaunchConfig:
        command = sublime.expand_variables(command, variables)
        command = [os.path.expanduser(arg) for arg in command]
        resolved_env = os.environ.copy()
        if env:
            for key, value in env.items():
                if key == "PATH":
                    resolved_env[key] = sublime.expand_variables(value, variables) + os.path.pathsep + resolved_env[key]
                else:
                    resolved_env[key] = sublime.expand_variables(value, variables)
        return LaunchConfig(command, resolved_env)

    @abstractmethod
    def start(
        self,
        command: list[str] | None,
        env: dict[str, str] | None,
        cwd: str | None,
        variables: dict[str, str],
        callbacks: TransportCallbacks,
    ) -> TransportWrapper:
        raise NotImplementedError


class StdioTransportConfig(TransportConfig):
    """
    The simplest of transport configs: launch the subprocess and communicate with it over standard I/O. This transport
    config requires a "command". This is the default transport config when only a "command" is specified in the
    ClientConfig.
    """

    @override
    def start(
        self,
        command: list[str] | None,
        env: dict[str, str] | None,
        cwd: str | None,
        variables: dict[str, str],
        callbacks: TransportCallbacks,
    ) -> TransportWrapper:
        if not command:
            raise RuntimeError('missing "command" to start a child process for running the language server')
        process = TransportConfig.resolve_launch_config(command, env, variables).start(
            cwd,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if not process.stdout or not process.stdin or not process.stderr:
            raise Exception('Failed to create transport config due to not being able to pipe stdio')
        return TransportWrapper(
            callback_object=callbacks,
            transport=FileObjectTransport(encode_json, decode_json, process.stdout, process.stdin),
            process=process,
            error_reader=ErrorReader(callbacks, process.stderr),
        )


class TcpClientTransportConfig(TransportConfig):
    """
    Transport for communicating to a language server that expects incoming client connections. The language server acts
    as the TCP server, this text editor acts as the TCP client. One can have a "command" with this transport
    configuration. In that case the subprocess is launched, and then the TCP connection is attempted. If no "command" is
    given, a TCP connection is still made. This can be used for cases where the language server is already running as
    part of some larger application, like Godot Editor.
    """

    def __init__(self, port: int | None) -> None:
        super().__init__()
        self._port = port
        if isinstance(self._port, int) and self._port <= 0:
            raise RuntimeError("invalid port number")

    @override
    def start(
        self,
        command: list[str] | None,
        env: dict[str, str] | None,
        cwd: str | None,
        variables: dict[str, str],
        callbacks: TransportCallbacks,
    ) -> TransportWrapper:
        port = _add_and_resolve_port_variable(variables, self._port)
        if command:
            process = TransportConfig.resolve_launch_config(command, env, variables).start(
                cwd,
                stdout=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            if not process.stdout:
                raise Exception('Failed to create transport config due to not being able to pipe stdout')
            error_reader = ErrorReader(callbacks, process.stdout)
        else:
            process = None
            error_reader = None
        return TransportWrapper(
            callback_object=callbacks,
            transport=SocketTransport(encode_json, decode_json, self._connect(port)),
            process=process,
            error_reader=error_reader,
        )

    def _connect(self, port: int) -> socket.socket:
        start_time = time.time()
        while time.time() - start_time < TCP_CONNECT_TIMEOUT:
            try:
                return socket.create_connection(('localhost', port))
            except ConnectionRefusedError:
                pass
        raise RuntimeError("failed to connect")


class TcpServerTransportConfig(TransportConfig):
    """
    Transport for communicating to a language server over TCP. The difference, however, is that this transport will
    start a TCP listener socket accepting new TCP cliet connections. Once a client connects to this text editor acting
    as the TCP server, we'll assume it's the language server we just launched. As such, this tranport requires a
    "command" for starting the language server subprocess.
    """

    def __init__(self, port: int | None) -> None:
        self._port = port
        if isinstance(self._port, int) and self._port <= 0:
            raise RuntimeError("invalid port number")

    @override
    def start(
        self,
        command: list[str] | None,
        env: dict[str, str] | None,
        cwd: str | None,
        variables: dict[str, str],
        callbacks: TransportCallbacks,
    ) -> TransportWrapper:
        if not command:
            raise RuntimeError('missing "command" to start a child process for running the language server')
        port = _add_and_resolve_port_variable(variables, self._port)
        launch = TransportConfig.resolve_launch_config(command, env, variables)
        listener_socket = socket.socket()
        listener_socket.bind(('localhost', port))
        listener_socket.settimeout(TCP_CONNECT_TIMEOUT)
        listener_socket.listen(1)
        process_task: PackagedTask[subprocess.Popen[bytes] | None] = Promise.packaged_task()
        process_promise, resolve_process = process_task

        # We need to be able to start the process while also awaiting a client connection.
        def start_in_background() -> None:
            # Sleep for one second, because the listener socket needs to be in the "accept" state before starting the
            # subprocess. This is hacky, and will get better when we can use asyncio.
            time.sleep(1)
            resolve_process(launch.start(
                cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE))

        thread = threading.Thread(target=start_in_background)
        thread.start()
        with closing(listener_socket):
            # Await one client connection (blocking!)
            sock, _ = listener_socket.accept()
        thread.join()
        process = process_promise.value
        if not process:
            raise Exception('Failed to create transport config from separate thread.')
        if not process.stderr:
            raise Exception('Failed to create transport config due to not being able to pipe stderr')
        error_reader = ErrorReader(callbacks, process.stderr)
        return TransportWrapper(
            callback_object=callbacks,
            transport=SocketTransport(encode_json, decode_json, sock),
            process=process,
            error_reader=error_reader,
        )


# --- Transports -------------------------------------------------------------------------------------------------------


class TransportCallbacks:
    def on_transport_close(self, exit_code: int, exception: Exception | None) -> None: ...

    def on_payload(self, payload: JSONRPCMessage) -> None: ...

    def on_stderr_message(self, message: str) -> None: ...


class Transport(ABC):
    def __init__(
        self,
        encoder: Callable[[JSONRPCMessage], bytes],
        decoder: Callable[[bytes], JSONRPCMessage]
    ) -> None:
        self._encoder = encoder
        self._decoder = decoder

    @abstractmethod
    def read(self) -> JSONRPCMessage | None:
        raise NotImplementedError

    @abstractmethod
    def write(self, payload: JSONRPCMessage) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError


class FileObjectTransport(Transport):
    def __init__(
        self,
        encoder: Callable[[JSONRPCMessage], bytes],
        decoder: Callable[[bytes], JSONRPCMessage],
        reader: IO[bytes] | BufferedIOBase,
        writer: IO[bytes] | BufferedIOBase,
    ) -> None:
        super().__init__(encoder, decoder)
        self._reader = reader
        self._writer = writer

    @override
    def read(self) -> JSONRPCMessage:
        headers: http.client.HTTPMessage | None = None
        try:
            headers = http.client.parse_headers(self._reader)
            content_length = headers.get("Content-Length")
            if not isinstance(content_length, str):
                raise TypeError("Missing Content-Length header")
            body = self._reader.read(int(content_length))
        except TypeError as ex:
            if str(headers) == "\n":
                # Expected on process stopping. Gracefully stop the transport.
                raise StopLoopError from None
            # Propagate server's output to the UI.
            raise Exception(f"Unexpected payload in server's stdout:\n\n{headers}") from ex
        try:
            return self._decoder(body)
        except Exception as ex:
            raise Exception(f"JSON decode error: {ex}") from ex

    @override
    def write(self, payload: JSONRPCMessage) -> None:
        body = self._encoder(payload)
        self._writer.writelines((f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"), body))
        self._writer.flush()

    @override
    def close(self) -> None:
        self._writer.close()
        self._reader.close()


class SocketTransport(FileObjectTransport):
    def __init__(
        self,
        encoder: Callable[[JSONRPCMessage], bytes],
        decoder: Callable[[bytes], JSONRPCMessage],
        sock: socket.socket
    ) -> None:
        reader_writer_pair = sock.makefile("rwb")
        super().__init__(encoder, decoder, reader_writer_pair, reader_writer_pair)
        self._socket = sock

    @override
    def close(self) -> None:
        super().close()
        self._socket.close()


# --- TransportWrapper -------------------------------------------------------------------------------------------------


@final
class TransportWrapper:
    """
    Double dispatch-like class that takes a (subclass of) Transport, and provides to a (subclass of) TransportCallbacks
    appropriately decoded messages. The TransportWrapper is also responsible for keeping the spawned child
    process around (if any), and also keeps track of the ErrorReader. It can be the case that there is no ErrorReader,
    for instance when talking to a remote TCP language server. So it can be None.
    """

    def __init__(
        self,
        callback_object: TransportCallbacks,
        transport: Transport,
        process: subprocess.Popen[bytes] | None,
        error_reader: ErrorReader | None,
    ) -> None:
        self._closed = False
        self._callback_object = weakref.ref(callback_object)
        self._transport = transport
        self._process = process
        self._error_reader = error_reader
        self._reader_thread = threading.Thread(target=self._read_loop)
        self._writer_thread = threading.Thread(target=self._write_loop)
        self._send_queue: Queue[JSONRPCMessage | None] = Queue(0)
        self._reader_thread.start()
        self._writer_thread.start()

    @property
    def process_args(self) -> Any:
        return self._process.args if self._process else None

    def send(self, payload: JSONRPCMessage) -> None:
        self._send_queue.put_nowait(payload)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._send_queue.put_nowait(None)
            _join_thread(self._writer_thread)
            _join_thread(self._reader_thread)
            if self._error_reader:
                self._error_reader.on_transport_close()
                self._error_reader = None
            if self._transport:
                self._transport.close()
                self._transport = None

    def _read_loop(self) -> None:
        exception = None
        try:
            while self._transport:
                if (payload := self._transport.read()) is None:
                    continue

                def invoke(p: JSONRPCMessage) -> None:
                    if self._closed:
                        return
                    if callback_object := self._callback_object():
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

    def _end(self, exception: Exception | None) -> None:
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
        exception: Exception | None = None
        try:
            while self._transport:
                if (d := self._send_queue.get()) is None:
                    break
                self._transport.write(d)
        except (BrokenPipeError, AttributeError):
            pass
        except Exception as ex:
            exception = ex
        self._end(exception)


class LaunchConfig:
    __slots__ = ("command", "env")

    def __init__(self, command: list[str], env: dict[str, str] | None = None) -> None:
        self.command: list[str] = command
        self.env: dict[str, str] = env or {}

    def start(
        self,
        cwd: str | None,
        stdin: int,
        stdout: int,
        stderr: int,
    ) -> subprocess.Popen[bytes]:
        startupinfo = _fixup_startup_args(self.command)
        return _start_subprocess(self.command, stdin, stdout, stderr, startupinfo, self.env, cwd)


# --- Utils -------------------------------------------------------------------------------------------------------

class ErrorReader:
    """
    Relays log messages from a raw stream to a (subclass of) TransportCallbacks.

    Because the various transport configurations want to listen to different streams, perhaps completely separate from
    the regular RPC transport, this is wrapped in a different class. For instance, a TCP client transport communicating
    via a socket, while it listens for log messages on the stdout/stderr streams of a spawned child process.
    """

    def __init__(self, callback_object: TransportCallbacks, reader: IO[bytes]) -> None:
        self._callback_object = weakref.ref(callback_object)
        self._reader = reader
        self._thread = threading.Thread(target=self._loop)
        self._thread.start()

    def on_transport_close(self) -> None:
        self._reader = None
        _join_thread(self._thread)

    def _loop(self) -> None:
        try:
            while self._reader:
                message = self._reader.readline().decode("utf-8", "replace")
                if not message:
                    continue
                callback_object = self._callback_object()
                if callback_object:
                    callback_object.on_stderr_message(message.rstrip())
                else:
                    break
        except (BrokenPipeError, AttributeError):
            pass
        except Exception as ex:
            exception_log("unexpected exception type in error reader", ex)


def encode_json(data: JSONRPCMessage) -> bytes:
    if orjson:
        return orjson.dumps(data)
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=False,
        check_circular=False,
        separators=(",", ":"),
    ).encode("utf-8")


def decode_json(message: bytes) -> JSONRPCMessage:
    if orjson:
        return orjson.loads(message)
    return json.loads(message.decode("utf-8"))


# --- Internal ---------------------------------------------------------------------------------------------------------


g_subprocesses: weakref.WeakSet[subprocess.Popen[bytes]] = weakref.WeakSet()


def kill_all_subprocesses() -> None:
    subprocesses = list(g_subprocesses)
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


def _fixup_startup_args(args: list[str]) -> Any:
    startupinfo = None
    if ST_PLATFORM == "windows":
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
    args: list[str],
    stdin: int,
    stdout: int,
    stderr: int,
    startupinfo: Any,
    env: dict[str, str],
    cwd: str | None,
) -> subprocess.Popen[bytes]:
    debug(f"starting {args} in {cwd or os.getcwd()}")
    process = subprocess.Popen(
        args=args,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        startupinfo=startupinfo,
        env=env,
        cwd=cwd,
    )
    g_subprocesses.add(process)
    return process


def _find_free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def _add_and_resolve_port_variable(variables: dict[str, str], port: int | None) -> int:
    if port is None:
        port = _find_free_port()
    variables["port"] = str(port)
    return port


def _join_thread(t: threading.Thread) -> None:
    if t.ident == threading.current_thread().ident:
        return
    try:
        t.join(2)
    except TimeoutError as ex:
        exception_log(f"failed to join {t.name} thread", ex)
