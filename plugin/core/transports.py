from __future__ import annotations
import itertools

from .aio import PortableTimeoutError
from .aio import TaskContainer
from .constants import ST_PLATFORM
from .logging import debug
from .logging import exception_log
from abc import ABC
from abc import abstractmethod
from enum import IntEnum
from pathlib import Path
from typing import Any
from typing import Callable
from typing import final
from typing import TYPE_CHECKING
from typing_extensions import override
import asyncio
import asyncio.subprocess
import contextlib
import json
import os
import shutil
import socket
import sublime
import subprocess
import time
import weakref

if TYPE_CHECKING:
    from .protocol import JSONRPCMessage

try:
    import orjson
except ImportError:
    orjson = None

TCP_CONNECT_TIMEOUT = 5  # seconds


class StopLoopError(Exception):
    pass


# --- Transport Configs ------------------------------------------------------------------------------------------------


class TransportConfig(ABC):
    """Config object that can start the transport."""

    @staticmethod
    def resolve_launch_config(
        command: list[str],
        env: dict[str, str] | None,
        variables: dict[str, str],
    ) -> LaunchConfig:
        """
        Given the state of this transport configuration, and the provided command/env/vars, create a small object
        that has resolved all variables to a concrete command to run.
        """
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
    async def start(
        self,
        command: list[str] | None,
        env: dict[str, str] | None,
        cwd: str | None,
        variables: dict[str, str],
        callbacks: TransportCallbacks,
    ) -> Transport:
        """Start a communication channel with the language server."""
        raise NotImplementedError


class StdioTransportConfig(TransportConfig):
    """
    The simplest of transport configs: launch the subprocess and communicate with it over standard I/O. This transport
    config requires a "command". This is the default transport config when only a "command" is specified in the
    ClientConfig.
    """

    @override
    async def start(
        self,
        command: list[str] | None,
        env: dict[str, str] | None,
        cwd: str | None,
        variables: dict[str, str],
        callbacks: TransportCallbacks,
    ) -> Transport:
        if not command:
            raise RuntimeError('missing "command" to start a child process for running the language server')
        launch = TransportConfig.resolve_launch_config(command, env, variables)
        process = await launch.start(
            cwd,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if not process.stdout or not process.stdin or not process.stderr:
            raise Exception('Failed to create transport config due to not being able to pipe stdio')
        return Transport(
            encode_json,
            decode_json,
            process.stdout,
            process.stdin,
            callbacks,
            process,
            launch.command,
            ErrorReader(callbacks, process.stderr),
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
    async def start(
        self,
        command: list[str] | None,
        env: dict[str, str] | None,
        cwd: str | None,
        variables: dict[str, str],
        callbacks: TransportCallbacks,
    ) -> Transport:
        port = _add_and_resolve_port_variable(variables, self._port)
        launch: LaunchConfig | None = None
        if command:
            launch = TransportConfig.resolve_launch_config(command, env, variables)
            process = await launch.start(
                cwd,
                stdout=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.STDOUT,
            )
            if not process.stdout:
                raise Exception('Failed to create transport config due to not being able to pipe stdout')
            error_reader = ErrorReader(callbacks, process.stdout)
        else:
            process = None
            error_reader = None
        start_time = time.time()
        delta = 0
        while delta < TCP_CONNECT_TIMEOUT:
            time_left = TCP_CONNECT_TIMEOUT - delta
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host='localhost', port=port, family=socket.AF_INET), timeout=time_left
                )
                return Transport(
                    encode_json,
                    decode_json,
                    reader,
                    writer,
                    callbacks,
                    process,
                    launch.command if launch else None,
                    error_reader,
                )
            except PortableTimeoutError:
                # We passed the TCP_CONNECT_TIMEOUT and the process didn't respond.
                break
            except (ConnectionRefusedError, OSError):
                # Can happen when the language server is still starting. Just wait a bit and retry.
                await asyncio.sleep(TCP_CONNECT_TIMEOUT / 10)
            delta = time.time() - start_time
        raise RuntimeError(f"Failed to connect to TCP port {port}")


class TcpServerTransportConfig(TransportConfig):
    """
    Transport for communicating to a language server over TCP. The difference, however, is that this transport will
    start a TCP listener socket accepting new TCP client connections. Once a client connects to this text editor acting
    as the TCP server, we'll assume it's the language server we just launched. As such, this tranport requires a
    "command" for starting the language server subprocess.
    """

    def __init__(self, port: int | None) -> None:
        self._port = port
        if isinstance(self._port, int) and self._port <= 0:
            raise RuntimeError("invalid port number")

    @override
    async def start(
        self,
        command: list[str] | None,
        env: dict[str, str] | None,
        cwd: str | None,
        variables: dict[str, str],
        callbacks: TransportCallbacks,
    ) -> Transport:
        if not command:
            raise RuntimeError('missing "command" to start a child process for running the language server')
        port = _add_and_resolve_port_variable(variables, self._port)
        launch = TransportConfig.resolve_launch_config(command, env, variables)

        class ClientConnectedCallback:
            def __init__(self) -> None:
                self.cv = asyncio.Condition()
                self.transport: Transport | None = None
                self.process: asyncio.subprocess.Process | None = None
                self.error_reader: ErrorReader | None = None

            async def __call__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                async with self.cv:
                    self.transport = Transport(
                        encode_json,
                        decode_json,
                        reader,
                        writer,
                        callbacks,
                        self.process,
                        launch.command,
                        self.error_reader,
                    )
                    self.cv.notify()

        callback = ClientConnectedCallback()
        async with callback.cv:
            server = await asyncio.start_server(callback, host='localhost', port=port, family=socket.AF_INET)
            try:
                await server.start_serving()
                process = await launch.start(
                    cwd,
                    stdout=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.STDOUT,
                )
                assert process.stdout
                callback.process = process
                callback.error_reader = ErrorReader(callbacks, process.stdout)
                try:
                    await asyncio.wait_for(callback.cv.wait(), timeout=TCP_CONNECT_TIMEOUT)
                except BaseException:
                    process.kill()
                    await process.wait()
                    raise
            finally:
                # Note: deliberately not awaiting server.wait_closed() here. Since Python 3.12, wait_closed() also
                # waits for all active connections to be dropped, not just the listening socket. But the connection
                # accepted above (if any) is the one we just handed off to the caller as the long-lived transport for
                # the language server session, so waiting for it to close here would deadlock forever.
                #
                # See: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.Server.wait_closed
                #
                # More background information: https://github.com/python/cpython/issues/104344
                server.close()
        assert callback.transport
        return callback.transport


# --- Transports -------------------------------------------------------------------------------------------------------


class TransportCallbacks:
    async def on_transport_close(self, exit_code: int, exception: Exception | None) -> None: ...

    async def on_payload(self, payload: JSONRPCMessage) -> None: ...

    def on_stderr_message(self, message: str) -> None: ...


async def parse_headers(reader: asyncio.StreamReader) -> dict[str, str]:
    headers: dict[str, str] = {}
    try:
        raw = await reader.readuntil(b'\r\n\r\n')
    except asyncio.IncompleteReadError as ex:
        # May happen when shutting down. parse_content_length will then return None,
        # which will cause the read loop to stop.
        if ex.partial:
            # Propagate server's output to the UI.
            raise
        return headers
    headers_bytes = raw.decode("ascii", "replace").rstrip()
    for line in headers_bytes.split("\r\n"):
        if ":" not in line:
            raise RuntimeError(f"Malformed header line from language server: {line!r}")
        key, value = line.split(":", 1)
        headers[key.lower()] = value
    return headers


async def parse_content_length(reader: asyncio.StreamReader) -> int | None:
    headers = await parse_headers(reader)
    if not headers:
        # clean EOF
        return None
    content_length = headers.get("content-length")
    if content_length is None:
        raise RuntimeError(f"Missing Content-Length header in language server output: {headers}")
    return int(content_length)


class _State(IntEnum):
    NEW = 0
    RUNNING = 1
    CLOSING = 2
    CLOSED = 3


@final
class Transport(TaskContainer):
    """
    Provides to a (subclass of) TransportCallbacks appropriately decoded messages. The Transport is also
    responsible for keeping the spawned child process around (if any), and also keeps track of the ErrorReader. It can
    be the case that there is no ErrorReader, for instance when talking to a remote TCP language server. So it can be
    None.
    """

    def __init__(
        self,
        encoder: Callable[[JSONRPCMessage], bytes],
        decoder: Callable[[bytes], JSONRPCMessage],
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        callback_object: TransportCallbacks,
        process: asyncio.subprocess.Process | None,
        process_args: list[str] | None,
        error_reader: ErrorReader | None,
    ) -> None:
        super().__init__()
        self._encoder = encoder
        self._decoder = decoder
        self._reader = reader
        self._writer = writer
        self._callback_object = weakref.ref(callback_object)
        self._process = process
        self._process_args = process_args
        self._error_reader: ErrorReader | None = error_reader
        self._task: asyncio.Task[None] | None = None
        self._state = _State.NEW
        self._closed_event = asyncio.Event()
        self._final_exit_code: int | None = None
        self._final_exception: Exception | None = None

    def start(self) -> None:
        """Start the message processing loop."""
        if self._state != _State.NEW:
            raise RuntimeError("transport started while it's not in the NEW state")
        self._task = asyncio.get_running_loop().create_task(self._read_loop())
        self._state = _State.RUNNING

    @property
    def process_args(self) -> list[str] | None:
        """
        The arguments for the process launched by this transport, or None if there is no process launched (such as with
        a remote TCP/websocket connection).
        """
        return self._process_args

    async def send(self, payload: JSONRPCMessage) -> None:
        """Write a JSON-RPC message."""
        if self._state == _State.RUNNING:
            await self._write(payload)
        elif self._state == _State.NEW:
            raise RuntimeError("missing call to .start()")

    async def send_bytes(self, payload: bytes) -> None:
        """Write raw bytes."""
        if self._state == _State.RUNNING:
            await self._write_bytes(payload)
        elif self._state == _State.NEW:
            raise RuntimeError("missing call to .start()")

    async def close(self) -> tuple[int | None, Exception | None]:
        """
        Stop the message loop and stop the process (if any).

        After returning from this coroutine function, the resources (tasks and process) are guaranteed cleaned up.
        It is safe to call this coroutine function concurrently from multiple coroutines.

        :returns: tuple of (exit code, exception)
        """
        await self._release_resources(wait_for_reader_task=True)
        return self._final_exit_code, self._final_exception

    async def _release_resources(self, wait_for_reader_task: bool) -> None:
        """Release all resources."""
        try:
            if self._state == _State.NEW:
                self._state = _State.CLOSING
                await self._kill_process()
            elif self._state == _State.RUNNING:
                self._state = _State.CLOSING
                with contextlib.suppress(BaseException):
                    await self.cancel_all_tasks()
                # Close the writer stream. This will cause the reader stream to close as well. In turn, that will cause
                # an EOF to appear on the reader stream. That will cause the _read_loop to stop naturally.
                self._writer.close()
                if self._process:
                    done, pending = await asyncio.wait([asyncio.create_task(self._process.wait())], timeout=5)
                    if self._process.returncode is None:
                        for t in itertools.chain(done, pending):
                            t.cancel()
                        # The process didn't stop. Just kill it now.
                        await self._kill_process()
                    else:
                        self._process, process = None, self._process
                        self._final_exit_code = process.returncode
            elif self._state == _State.CLOSING:
                await self._closed_event.wait()
            # else it's the CLOSED state
        finally:
            old_state, self._state = self._state, _State.CLOSED
            if self._error_reader:
                self._error_reader.on_transport_close()
                self._error_reader = None
            self._writer.close()
            with contextlib.suppress(ConnectionError):
                await self._writer.wait_closed()
            if old_state == _State.CLOSING:
                self._closed_event.set()
            if wait_for_reader_task and self._task:
                _done, pending = await asyncio.wait([self._task], timeout=5)
                if len(pending) > 0:
                    # We waited 5 seconds; inject an asyncio.CancelledError into the _read_loop task now.
                    self._task.cancel()

    async def _read(self) -> JSONRPCMessage:
        """Read one JSON-RPC message."""
        content_length = await parse_content_length(self._reader)
        if content_length is None:
            raise StopLoopError
        body = await self._reader.readexactly(content_length)
        try:
            return self._decoder(body)
        except Exception as ex:
            raise Exception(f"JSON decode error: {ex}") from ex

    async def _write(self, payload: JSONRPCMessage) -> None:
        """Write a JSON-RPC message."""
        body = self._encoder(payload)
        self._writer.writelines((f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"), body))
        # ConnectionError can happen when the lang server is shut down or the connection is severed in some way. Just
        # ignore it, there's other logic that will make the transport shut down.
        with contextlib.suppress(ConnectionError):
            await self._writer.drain()

    async def _write_bytes(self, payload: bytes) -> None:
        """Write raw bytes."""
        self._writer.write(payload)
        with contextlib.suppress(ConnectionError):
            await self._writer.drain()

    async def _read_loop(self) -> None:
        """Read JSON-RPC messages in a loop forever, and dispatch them to the TransportCallbacks object."""
        try:
            while True:
                payload = await self._read()
                if callback_object := self._callback_object():
                    # Don't block the read loop on handler execution. Otherwise, a request handler that sends its own
                    # request to the server and awaits the response would deadlock: the read loop is stuck waiting for
                    # the handler, but the handler is waiting for a response that can only be read by the read loop.
                    self.create_task(callback_object.on_payload(payload))
        except (AttributeError, BrokenPipeError, StopLoopError, asyncio.CancelledError):
            # asyncio.Cancelled is swallowed on purpose. It's needed so the tail of this method runs to completion.
            pass
        except Exception as ex:
            self._final_exception = ex
        # Release all resources (streams, maybe process).
        #
        # If the process crashed or a stream stopped due to a broken socket, then calling _release_resources will
        # ensure the resources are torn down.
        #
        # If a coroutine called the close() method, then the writer stream was closed and we exited the loop
        # "naturally". But then close() is also calling _release_resources. Then this call will enter the CLOSING case
        # and wait for the asyncio.Event to signal.
        #
        await self._release_resources(wait_for_reader_task=False)
        if callback_object := self._callback_object():
            await callback_object.on_transport_close(self._final_exit_code or 0, self._final_exception)

    async def _kill_process(self) -> None:
        """Kill the process (if any). We don't care about the return code when killing it."""
        if not self._process:
            # There is no process to kill.
            return
        self._process, process = None, self._process
        if process.returncode is not None:
            # The process has already stopped.
            self._final_exit_code = process.returncode
            return
        try:
            process.kill()
            await process.wait()
        except Exception as ex:
            exception_log("strange exception during process kill", ex)


class LaunchConfig:
    """Small object that can start a process."""

    __slots__ = ("command", "env")

    def __init__(self, command: list[str], env: dict[str, str] | None = None) -> None:
        self.command: list[str] = command
        self.env: dict[str, str] = env or {}

    async def start(
        self,
        cwd: str | None,
        stdin: int,
        stdout: int,
        stderr: int,
    ) -> asyncio.subprocess.Process:
        """Start a process."""
        startupinfo = _fixup_startup_args(self.command)
        return await _start_subprocess(self.command, stdin, stdout, stderr, startupinfo, self.env, cwd)


# --- Utils -------------------------------------------------------------------------------------------------------


class ErrorReader:
    """
    Relays log messages from a raw stream to a (subclass of) TransportCallbacks.

    Because the various transport configurations want to listen to different streams, perhaps completely separate from
    the regular RPC transport, this is wrapped in a different class. For instance, a TCP client transport communicating
    via a socket, while it listens for log messages on the stdout/stderr streams of a spawned child process.
    """

    def __init__(self, callback_object: TransportCallbacks, reader: asyncio.StreamReader) -> None:
        self._callback_object = weakref.ref(callback_object)
        self._reader = reader
        self._task = asyncio.get_running_loop().create_task(self._loop())

    def on_transport_close(self) -> None:
        self._reader = None
        self._task.cancel()

    async def _loop(self) -> None:
        try:
            while self._reader:
                raw = await self._reader.readline()
                if not raw:
                    break
                message = raw.decode("utf-8", "replace")
                if callback_object := self._callback_object():
                    callback_object.on_stderr_message(message.rstrip())
                else:
                    break
        except (BrokenPipeError, AttributeError, asyncio.CancelledError):
            # debug(f"exiting from ErrorReader._loop with expected error (which is: {type(ex)}, message: {ex})")
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


g_subprocesses: weakref.WeakSet[asyncio.subprocess.Process] = weakref.WeakSet()


async def kill_all_subprocesses() -> None:
    subprocesses = list(g_subprocesses)
    for p in subprocesses:
        try:
            p.kill()
        except Exception:
            pass
    await asyncio.gather(*[p.wait() for p in subprocesses], return_exceptions=True)


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


async def _start_subprocess(
    args: list[str],
    stdin: int,
    stdout: int,
    stderr: int,
    startupinfo: Any,
    env: dict[str, str],
    cwd: str | None,
) -> asyncio.subprocess.Process:
    if cwd and not Path(cwd).is_dir():  # ruff: ignore[blocking-path-method-in-async-function]
        debug(f"working directory {cwd} does not exist, using current working directory instead")
        cwd = os.getcwd()
    debug(f"starting {args} in {cwd or os.getcwd()}")
    process = await asyncio.create_subprocess_exec(
        *args,
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
