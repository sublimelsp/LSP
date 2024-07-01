from __future__ import annotations
from .logging import exception_log, debug
from abc import abstractmethod
from contextlib import closing
from functools import partial
from queue import Queue
from typing import Any, Callable, Generic, IO, Protocol, Sequence, TypeVar
import http.client
import http
import io
import json
import os
import shutil
import socket
import sublime
import subprocess
import contextlib
import threading
import time
import weakref
import ssl


TCP_CONNECT_TIMEOUT = 5  # seconds
T = TypeVar("T")
T_contra = TypeVar("T_contra", contravariant=True)


def _set_inheritable(inherit_file_descriptors: Sequence[int] | None, value: bool) -> None:
    if inherit_file_descriptors and sublime.platform() == "windows":
        for file_descriptor in inherit_file_descriptors:
            os.set_handle_inheritable(file_descriptor, value)  # type: ignore


class LaunchConfig:
    __slots__ = ("command", "env")

    def __init__(self, command: list[str], env: dict[str, str] = {}) -> None:
        self.command: list[str] = command
        self.env: dict[str, str] = env

    def start(
        self,
        cwd: str | None,
        stdout: int,
        stdin: int,
        stderr: int,
        inherit_file_descriptors: Sequence[int] | None = None,
    ) -> subprocess.Popen:
        startupinfo = _fixup_startup_args(self.command, inherit_file_descriptors)
        _set_inheritable(inherit_file_descriptors, True)
        pass_fds = inherit_file_descriptors if inherit_file_descriptors and sublime.platform() != "windows" else tuple()
        try:
            return _start_subprocess(self.command, stdout, stdin, stderr, startupinfo, self.env, cwd, pass_fds)
        finally:
            _set_inheritable(inherit_file_descriptors, False)


class StopLoopError(Exception):
    pass


class Transport(Generic[T]):
    def __init__(self, encoder: Callable[[T], bytes], decoder: Callable[[bytes], T], http_headers: bool) -> None:
        self._encoder = encoder
        self._decoder = decoder
        self._http_headers = http_headers

    def read(self) -> T:
        raise NotImplementedError()

    def write(self, payload: T) -> None:
        raise NotImplementedError()

    def close(self) -> None:
        raise NotImplementedError()


class TransportCallbacks(Protocol[T_contra]):
    def on_transport_close(self, exit_code: int, exception: Exception | None) -> None: ...

    def on_payload(self, payload: T_contra) -> None: ...

    def on_stderr_message(self, message: str) -> None: ...


def _join_thread(t: threading.Thread) -> None:
    if t.ident == threading.current_thread().ident:
        return
    try:
        t.join(2)
    except TimeoutError as ex:
        exception_log(f"failed to join {t.name} thread", ex)


class ErrorReader(Generic[T]):
    """
    Responsible for relaying log messages from a raw stream to a (subclass of) TransportCallbacks. Because the various
    transport configurations want to listen to different streams, perhaps completely separate from the regular RPC
    transport, this is wrapped in a different class. For instance, a TCP client transport communicating via a socket,
    while it listens for log messages on the stdout/stderr streams of a spawned child process.
    """

    def __init__(self, callback_object: TransportCallbacks[T], reader: IO[bytes]) -> None:
        self._callback_object = weakref.ref(callback_object)
        self._reader = reader
        self._thread = threading.Thread(target=self._loop)
        self._thread.start()

    def __del__(self) -> None:
        _join_thread(self._thread)

    def _loop(self) -> None:
        try:
            while self._reader:
                message = self._reader.readline().decode("utf-8", "replace")
                if message == "":
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


class TransportWrapper(Generic[T]):
    """
    Double dispatch-like class that takes a (subclass of) Transport, and provides to a (subclass of) TransportCallbacks
    appropriately decoded messages of type T. The TransportWrapper is also responsible for keeping the spawned child
    process around (if any), and also keeps track of the ErrorReader. It can be the case that there is no ErrorReader,
    for instance when talking to a remote TCP language server. So it can be None.
    """

    def __init__(
        self,
        callback_object: TransportCallbacks[T],
        transport: Transport[T],
        process: subprocess.Popen | None,
        error_reader: ErrorReader | None,
    ) -> None:
        self._closed = False
        self._callback_object = weakref.ref(callback_object)
        self._transport = transport
        self._process = process
        self._error_reader = error_reader
        self._reader_thread = threading.Thread(target=self._read_loop)
        self._writer_thread = threading.Thread(target=self._write_loop)
        self._send_queue: Queue[T | None] = Queue(0)
        self._reader_thread.start()
        self._writer_thread.start()

    @property
    def process_args(self) -> Any:
        return self._process.args if self._process else None

    def send(self, payload: T) -> None:
        self._send_queue.put_nowait(payload)

    def close(self) -> None:
        if not self._closed:
            self._send_queue.put_nowait(None)
            self._transport.close()
            self._closed = True

    def __del__(self) -> None:
        self.close()
        _join_thread(self._writer_thread)
        _join_thread(self._reader_thread)

    def _read_loop(self) -> None:
        exception = None
        try:
            while True:
                payload = self._transport.read()
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
            while True:
                d = self._send_queue.get()
                if d is None:
                    break
                self._transport.write(d)
        except (BrokenPipeError, AttributeError):
            pass
        except Exception as ex:
            exception = ex
        self._end(exception)


def encode_json(data: dict[str, Any]) -> bytes:
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=False,
        check_circular=False,
        separators=(",", ":"),
    ).encode("utf-8")


def decode_json(message: bytes) -> dict[str, Any]:
    return json.loads(message.decode("utf-8"))


class FileObjectTransport(Transport[T]):
    def __init__(
        self,
        encoder: Callable[[T], bytes],
        decoder: Callable[[bytes], T],
        http_headers: bool,
        reader: io.BufferedIOBase,
        writer: io.BufferedIOBase,
    ) -> None:
        super().__init__(encoder, decoder, http_headers)
        self._reader = reader
        self._writer = writer

    def read(self) -> T:
        headers: http.client.HTTPMessage | None = None
        try:
            if self._http_headers:
                headers = http.client.parse_headers(self._reader)
                content_length = headers.get("Content-Length")
                if not isinstance(content_length, str):
                    raise Exception("missing Content-Length header")
                body = self._reader.read(int(content_length))
            else:
                body = self._reader.readline()
                if not body or body == b"\n":
                    raise StopLoopError()
        except TypeError:
            if str(headers) == "\n":
                # Expected on process stopping. Gracefully stop the transport.
                raise StopLoopError()
            else:
                # Propagate server's output to the UI.
                raise Exception(f"Unexpected payload in server's stdout:\n\n{headers}")
        try:
            return self._decoder(body)
        except Exception as ex:
            raise Exception(f"JSON decode error: {ex}")

    def write(self, payload: T) -> None:
        body = self._encoder(payload)
        if self._http_headers:
            self._writer.writelines((f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"), body))
        else:
            self._writer.writelines((body, b"\n"))
        self._writer.flush()

    def close(self) -> None:
        self._writer.close()
        self._reader.close()


class SocketTransport(FileObjectTransport[T]):
    def __init__(
        self, encoder: Callable[[T], bytes], decoder: Callable[[bytes], T], http_headers: bool, sock: socket.socket
    ) -> None:
        reader_writer_pair: io.BufferedRWPair = sock.makefile("rwb")
        super().__init__(encoder, decoder, http_headers, reader_writer_pair, reader_writer_pair)
        self._socket = sock

    def close(self) -> None:
        super().close()
        self._socket.close()


class WebSocketTransport(Transport[T]):
    def read(self) -> T:
        raise NotImplementedError()

    def write(self, payload: T) -> None:
        raise NotImplementedError()

    def close(self) -> None:
        raise NotImplementedError()


class DuplexPipeTransport(SocketTransport[T]):
    def __init__(
        self,
        encoder: Callable[[T], bytes],
        decoder: Callable[[bytes], T],
        http_headers: bool,
        sock1: socket.socket,
        sock2: socket.socket,
    ) -> None:
        super().__init__(encoder, decoder, http_headers, sock2)
        self._sock1 = sock1

    def close(self) -> None:
        super().close()
        self._sock1.close()


class TransportConfig:
    """
    Responsible for instantiating a TransportWrapper, which is the object that does the actual RPC communication.
    """

    __slots__ = ("_http_headers",)

    def __init__(self, http_headers: bool = True) -> None:
        self._http_headers = http_headers

    @property
    def http_headers(self) -> bool:
        return self._http_headers

    def requires_launch_config(self) -> bool:
        return False

    def _resolve_launch_config(
        self,
        command: list[str],
        env: dict[str, str | list[str]] | None,
        variables: dict[str, str],
    ) -> LaunchConfig:
        command = sublime.expand_variables(command, variables)
        command = [os.path.expanduser(arg) for arg in command]
        resolved_env = os.environ.copy()
        for key, value in env.items() if isinstance(env, dict) else {}:
            if isinstance(value, list):
                value = os.path.pathsep.join(value)
            if key == "PATH":
                resolved_env[key] = sublime.expand_variables(value, variables) + os.path.pathsep + resolved_env[key]
            else:
                resolved_env[key] = sublime.expand_variables(value, variables)
        return LaunchConfig(command, resolved_env)

    @abstractmethod
    def start(
        self,
        command: list[str] | None,
        env: dict[str, str | list[str]] | None,
        cwd: str | None,
        variables: dict[str, str],
        callbacks: TransportCallbacks[dict[str, Any]],
    ) -> TransportWrapper[dict[str, Any]]:
        raise NotImplementedError()


class StdioTransportConfig(TransportConfig):
    """
    The simplest of transport configs: launch the subprocess and communicate with it over standard I/O. This transport
    config requires a "command". This is the default transport config when only a "command" is specified in the
    ClientConfig.
    """

    __slots__ = ()

    def __init__(self, http_headers: bool) -> None:
        super().__init__(http_headers)

    def start(
        self,
        command: list[str] | None,
        env: dict[str, str | list[str]] | None,
        cwd: str | None,
        variables: dict[str, str],
        callbacks: TransportCallbacks[dict[str, Any]],
    ) -> TransportWrapper:
        if not command:
            raise RuntimeError('missing "command" to start a child process for running the language server')
        process = self._resolve_launch_config(command, env, variables).start(
            cwd,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return TransportWrapper(
            callback_object=callbacks,
            transport=FileObjectTransport(encode_json, decode_json, self.http_headers, process.stdout, process.stdin),  # type: ignore # noqa: E501
            process=process,
            error_reader=ErrorReader(callbacks, process.stderr),  # type: ignore
        )


class TcpClientTransportConfig(TransportConfig):
    """
    Transport for communicating to a language server that expects incoming client connections. The language server acts
    as the TCP server, this text editor acts as the TCP client. One can have a "command" with this transport
    configuration. In that case the subprocess is launched, and then the TCP connection is attempted. If no "command" is
    given, a TCP connection is still made. This can be used for cases where the language server is already running as
    part of some larger application, like Godot Editor.
    """

    __slots__ = ("_hostname", "_port")

    def __init__(self, http_headers: bool, hostname: str | None, port: int | None) -> None:
        super().__init__(http_headers)
        self._hostname = hostname
        self._port = port
        if isinstance(self._port, int) and self._port <= 0:
            raise RuntimeError("invalid port number")

    def _connect(self, port: int) -> socket.socket:
        start_time = time.time()
        last_exception: Exception | None = None
        while time.time() - start_time < TCP_CONNECT_TIMEOUT:
            try:
                return socket.create_connection((self._hostname or "", port))
            except Exception as ex:
                last_exception = ex
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("failed to connect")

    def start(
        self,
        command: list[str] | None,
        env: dict[str, str | list[str]] | None,
        cwd: str | None,
        variables: dict[str, str],
        callbacks: TransportCallbacks[dict[str, Any]],
    ) -> TransportWrapper:
        port = _add_and_resolve_port_variable(variables, self._port)
        if command:
            process = self._resolve_launch_config(command, env, variables).start(
                cwd,
                stdout=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            error_reader: ErrorReader | None = ErrorReader(callbacks, process.stdout)  # type: ignore
        else:
            process = None
            error_reader = None
        return TransportWrapper(
            callback_object=callbacks,
            transport=SocketTransport(encode_json, decode_json, self.http_headers, self._connect(port)),
            process=process,
            error_reader=error_reader,
        )


class TcpServerTransportConfig(TransportConfig):
    """
    Transport for communicating to a language server over TCP. The difference, however, is that this transport will
    start a TCP listener socket accepting new TCP cliet connections. Once a client connects to this text editor acting
    as the TCP server, we'll assume it's the language server we just launched. As such, this tranport requires a
    "command" for starting the language server subprocess.
    """

    __slots__ = ("_port",)

    def __init__(self, http_headers: bool, port: int | None = None) -> None:
        super().__init__(http_headers)
        self._port = port

    def start(
        self,
        command: list[str] | None,
        env: dict[str, str | list[str]] | None,
        cwd: str | None,
        variables: dict[str, str],
        callbacks: TransportCallbacks[dict[str, Any]],
    ) -> TransportWrapper:
        if not command:
            raise RuntimeError('missing "command" to start a child process for running the language server')
        port = _add_and_resolve_port_variable(variables, self._port)
        launch = self._resolve_launch_config(command, env, variables)
        listener_socket = socket.socket()
        listener_socket.bind(("", port))
        listener_socket.settimeout(TCP_CONNECT_TIMEOUT)
        listener_socket.listen(TCP_CONNECT_TIMEOUT)
        process: subprocess.Popen | None = None

        # We need to be able to start the process while also awaiting a client connection.
        def start_in_background() -> None:
            nonlocal process
            # Sleep for one second, because the listener socket needs to be in the "accept" state before starting the
            # subprocess. This is hacky, and will get better when we can use asyncio.
            time.sleep(1)
            process = launch.start(
                cwd,
                stdout=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )

        thread = threading.Thread(target=start_in_background)
        thread.start()
        with closing(listener_socket):
            # Await one client connection (blocking!)
            sock, _ = listener_socket.accept()
        thread.join()

        error_reader = ErrorReader(callbacks, process.stdout)  # type: ignore
        return TransportWrapper(
            callback_object=callbacks,
            transport=SocketTransport(encode_json, decode_json, self.http_headers, sock),
            process=process,
            error_reader=error_reader,
        )


class TlsClientTransportConfig(TcpClientTransportConfig):
    """
    Exactly like the TCP client transport, except we wrap the communication in secure TLS/SSL.
    """

    __slots__ = ()

    def _connect(self, port: int) -> socket.socket:
        # TODO: Check if a call to ssl.create_default_context() is needed here.
        return ssl.wrap_socket(super()._connect(port))


class WebSocketClientTransportConfig(TransportConfig):
    """
    Transport configuration for connecting, as an HTTP(S) client, to an HTTP(S) server. The HTTP(S) server is expected
    to make the WebSocket upgrade negotiation, after which we upgrade to WebSocket and will then start talking the LSP
    protocol. This transport can have a "command", in which case we start the subprocess using the provided "command",
    and then start the websocket connection.
    """

    __slots__ = ("_hostname", "_port", "_secure")

    def __init__(
        self,
        http_headers: bool,
        hostname: str | None,
        port: int | None,
        secure: bool = False,
    ) -> None:
        super().__init__(http_headers)
        self._hostname = hostname
        self._port = port
        self._secure = secure

    @property
    def port(self) -> int:
        if isinstance(self._port, int):
            return self._port
        return http.client.HTTPS_PORT if self._secure else http.client.HTTP_PORT


class DuplexPipeTransportConfig(TransportConfig):
    """
    Transport configuration for communicating with a process using a "duplex pipe" construction. The spawned subprocess
    is informed of the pipe's file descriptor with an environment variable. The pipe file descriptor handle is inherited
    by the child process.

    On Linux and macOS, this is implemented using AF_UNIX socketpairs:
    https://www.man7.org/linux/man-pages/man7/unix.7.html

    !!! TODO !!!
    On Windows, this is implemented using NamedPipes: https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipes
    """

    __slots__ = ("_child_fileno_env_key",)

    def __init__(self, http_headers: bool, child_fileno_env_key: str) -> None:
        super().__init__(http_headers)
        self._child_fileno_env_key = child_fileno_env_key

    def start(
        self,
        command: list[str] | None,
        env: dict[str, str | list[str]] | None,
        cwd: str | None,
        variables: dict[str, str],
        callbacks: TransportCallbacks[dict[str, Any]],
    ) -> TransportWrapper:
        if not command:
            raise RuntimeError('missing "command" to start a child process for running the language server')
        if env is None:
            env = {}
        # !!! TODO !!! windows named pipes
        sock1, sock2 = socket.socketpair()
        sock1.set_inheritable(True)
        env[self._child_fileno_env_key] = str(sock1.fileno())
        process = self._resolve_launch_config(command, env, variables).start(
            cwd,
            stdout=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            inherit_file_descriptors=(sock1.fileno(),),
        )
        error_reader = ErrorReader(callbacks, process.stdout)  # type: ignore
        return TransportWrapper(
            callback_object=callbacks,
            transport=DuplexPipeTransport(encode_json, decode_json, self.http_headers, sock1, sock2),
            process=process,
            error_reader=error_reader,
        )


_subprocesses: weakref.WeakSet[subprocess.Popen] = weakref.WeakSet()


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


def _fixup_startup_args(args: list[str], inherit_file_descriptors: Sequence[int] | None = None) -> Any:
    startupinfo = None
    if sublime.platform() == "windows":
        startupinfo = subprocess.STARTUPINFO()  # type: ignore
        if inherit_file_descriptors:
            startupinfo.lpAttributeList = {"handle_list": inherit_file_descriptors}
        startupinfo.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW  # type: ignore
        executable_arg = args[0]
        _, ext = os.path.splitext(executable_arg)
        if len(ext) < 1:
            path_to_executable = shutil.which(executable_arg)
            # what extensions should we append so CreateProcess can find it?
            # node has .cmd
            # dart has .bat
            # python has .exe wrappers - not needed
            for extension in [".cmd", ".bat"]:
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
    pass_fds: Sequence[int],
) -> subprocess.Popen:
    debug(f"starting {args} in {cwd if cwd else os.getcwd()}")
    if pass_fds:
        debug(f"inheriting file descriptors: {pass_fds}")
    process = subprocess.Popen(
        args=args,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        startupinfo=startupinfo,
        env=env,
        cwd=cwd,
        pass_fds=pass_fds,
    )
    debug("hello world")
    _subprocesses.add(process)
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
