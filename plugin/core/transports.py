from __future__ import annotations

from .constants import ST_PLATFORM
from .logging import debug
from .logging import exception_log
from .promise import PackagedTask
from .promise import Promise
from .protocol import JSONRPCMessage
from abc import ABC
from abc import abstractmethod
from asyncio.subprocess import Process
from contextlib import closing
from functools import partial
from io import BufferedIOBase
from queue import Queue
from typing import Any
from typing import Callable
from typing import final
from typing import IO
from typing_extensions import override
import asyncio
import contextlib
import http.client
import json
import os
import shutil
import socket
import sublime
import sublime_aio
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
    ) -> TransportWrapper:
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
    ) -> TransportWrapper:
        if not command:
            raise RuntimeError('missing "command" to start a child process for running the language server')
        process = await TransportConfig.resolve_launch_config(command, env, variables).start(
            cwd,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if not process.stdout or not process.stdin or not process.stderr:
            raise Exception('Failed to create transport config due to not being able to pipe stdio')
        return TransportWrapper(
            callback_object=callbacks,
            transport=StreamTransport(encode_json, decode_json, process.stdout, process.stdin),
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
    async def start(
        self,
        command: list[str] | None,
        env: dict[str, str] | None,
        cwd: str | None,
        variables: dict[str, str],
        callbacks: TransportCallbacks,
    ) -> TransportWrapper:
        port = _add_and_resolve_port_variable(variables, self._port)
        if command:
            process = await TransportConfig.resolve_launch_config(command, env, variables).start(
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
        reader, writer = await asyncio.wait_for(asyncio.open_connection('localhost', port), timeout=TCP_CONNECT_TIMEOUT)
        return TransportWrapper(
            callback_object=callbacks,
            transport=StreamTransport(encode_json, decode_json, reader, writer),
            process=process,
            error_reader=error_reader,
        )


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
    ) -> TransportWrapper:
        if not command:
            raise RuntimeError('missing "command" to start a child process for running the language server')
        port = _add_and_resolve_port_variable(variables, self._port)
        launch = TransportConfig.resolve_launch_config(command, env, variables)

        class ClientConnectedCallback:

            def __init__(self) -> None:
                self.cv = asyncio.Condition()
                self.wrapper: TransportWrapper | None = None
                self.process: asyncio.subprocess.Process | None = None
                self.error_reader: ErrorReader | None = None

            async def __call__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                async with self.cv:
                    transport = StreamTransport(encode_json, decode_json, reader, writer)
                    self.wrapper = TransportWrapper(callbacks, transport, self.process, self.error_reader)
                    self.cv.notify()

        callback = ClientConnectedCallback()
        async with callback.cv:
            server = await asyncio.start_server(callback, port=port)
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
                except Exception:
                    process.kill()
                    await process.wait()
                    raise
            finally:
                server.close()
                await server.wait_closed()
        assert callback.wrapper
        return callback.wrapper


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
    async def read(self) -> JSONRPCMessage | None:
        raise NotImplementedError

    @abstractmethod
    async def write(self, payload: JSONRPCMessage) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError


async def parse_headers(reader: asyncio.StreamReader) -> dict[str, str] | None:
    headers: dict[str, str] = {}
    while True:
        line = await reader.readline()
        if not line:
            # stream closed
            return None
        line = line.decode("ascii").strip()
        if not line:
            # end of headers
            break
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


class StreamTransport(Transport):
    def __init__(
        self,
        encoder: Callable[[JSONRPCMessage], bytes],
        decoder: Callable[[bytes], JSONRPCMessage],
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        super().__init__(encoder, decoder)
        self._reader = reader
        self._writer = writer

    @override
    async def read(self) -> JSONRPCMessage:
        headers: dict[str, str] | None = None
        try:
            headers = await parse_headers(self._reader)
            if headers is None:
                raise StopLoopError
            content_length = headers.get("content-length")
            if not isinstance(content_length, str):
                raise TypeError("Missing Content-Length header")
            body = await self._reader.read(int(content_length))
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
    async def write(self, payload: JSONRPCMessage) -> None:
        body = self._encoder(payload)
        self._writer.writelines((f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"), body))
        await self._writer.drain()

    @override
    async def close(self) -> None:
        self._writer.close()
        await self._writer.wait_closed()


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
        process: asyncio.subprocess.Process | None,
        error_reader: ErrorReader | None,
    ) -> None:
        self._callback_object = weakref.ref(callback_object)
        self._transport: Transport | None = transport
        self._process = process
        self._error_reader: ErrorReader | None = error_reader
        self._future = sublime_aio.run_coroutine(self._read_loop())

    @property
    def process_args(self) -> Any:
        return self._process.args if self._process else None

    async def send(self, payload: JSONRPCMessage) -> None:
        if self._transport:
            await self._transport.write(payload)

    async def close(self) -> None:
        if self._transport is not None:
            if self._error_reader:
                self._error_reader.on_transport_close()
                self._error_reader = None
            if self._transport:
                await self._transport.close()
                self._transport = None

    async def _read_loop(self) -> None:
        exception = None
        try:
            while self._transport:
                if (payload := await self._transport.read()) is None:
                    continue

                def invoke(p: JSONRPCMessage) -> None:
                    if not self._transport:
                        return
                    if callback_object := self._callback_object():
                        callback_object.on_payload(p)

                sublime.set_timeout_async(partial(invoke, payload))
        except (AttributeError, BrokenPipeError, StopLoopError):
            pass
        except Exception as ex:
            exception = ex
        if exception:
            await self._end(exception)

    async def _end(self, exception: Exception | None) -> None:
        exit_code: int | None = None
        if self._process:
            if not exception:
                try:
                    # Allow the process to stop itself.
                    exit_code = await asyncio.wait_for(self._process.wait(), timeout=1)
                except (AttributeError, ProcessLookupError, asyncio.TimeoutError):
                    pass
            if exit_code is None:
                try:
                    # The process didn't stop itself. Terminate!
                    self._process.kill()
                    # still wait for the process to die, or zombie processes might be the result
                    # Ignore the exit code in this case, it's going to be something non-zero because we sent SIGKILL.
                    await self._process.wait()
                except (AttributeError, ProcessLookupError):
                    pass
                except Exception as ex:
                    exception = ex  # TODO: Old captured exception is overwritten

        def invoke() -> None:
            callback_object = self._callback_object()
            if callback_object:
                callback_object.on_transport_close(exit_code or 0, exception)

        sublime.set_timeout_async(invoke)
        await self.close()


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
        self._future = sublime_aio.run_coroutine(self._loop())

    def on_transport_close(self) -> None:
        self._reader = None
        self._future.cancel()

    async def _loop(self) -> None:
        try:
            while self._reader:
                message = (await self._reader.readline()).decode("utf-8", "replace")
                if not message:
                    continue
                callback_object = self._callback_object()
                if callback_object:
                    callback_object.on_stderr_message(message.rstrip())
                else:
                    break
        except (BrokenPipeError, AttributeError, asyncio.CancelledError):
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
    await asyncio.gather(*[p.wait() for p in subprocesses])


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
    debug(f"starting {args} in {cwd or os.getcwd()}")
    process = await asyncio.create_subprocess_exec(
        args[0],
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
