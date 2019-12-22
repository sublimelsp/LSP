"""
A simple test server for integration tests.

Only understands stdio.
Uses the asyncio module and mypy types, so you'll need a modern Python.

To make this server reply to requests, send the $test/setResponse notification.

To await a method that this server should eventually (or already has) received,
send the $test/getReceived request. If the method was already received, it will
return None immediately. Otherwise, it will wait for the method. You should
have a timeout in your tests to ensure your tests won't hang forever.

TODO: Make this server send out notifications somehow.
TODO: Untested on Windows.
"""
from argparse import ArgumentParser
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import asyncio
import json
import os
import sys


__package__ = "server"
__version__ = "0.9.3"


if sys.version_info[0] < 3:
    print("only works for python3.5 and higher")
    exit(1)
if sys.version_info[1] < 5:
    print("only works for python3.5 and higher")
    exit(1)


StringDict = Dict[str, Any]
PayloadLike = Union[List[StringDict], StringDict, None]

ENCODING = "utf-8"


class ErrorCode(IntEnum):
    # Defined by JSON RPC
    ParseError = -32700
    InvalidRequest = -32600
    MethodNotFound = -32601
    InvalidParams = -32602
    InternalError = -32603
    serverErrorStart = -32099
    serverErrorEnd = -32000
    ServerNotInitialized = -32002
    UnknownErrorCode = -32001

    # Defined by the protocol
    RequestCancelled = -32800
    ContentModified = -32801


class Error(Exception):

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code

    def to_lsp(self) -> StringDict:
        return {"code": self.code, "message": super().__str__()}

    def __str__(self) -> str:
        return f"{super().__str__()} ({self.code})"


def jsonrpc() -> StringDict:
    return {"jsonrpc": "2.0"}


def make_response(request_id: int, params: PayloadLike) -> StringDict:
    return {**jsonrpc(), "id": request_id, "result": params}


def make_error_response(request_id: int, err: Error) -> StringDict:
    return {**jsonrpc(), "id": request_id, "error": err.to_lsp()}


def make_notification(method: str, params: PayloadLike) -> StringDict:
    return {**jsonrpc(), "method": method, "params": params}


def make_request(method: str, request_id: int, params: PayloadLike) -> StringDict:
    return {**jsonrpc(), "method": method, "id": request_id, "params": params}


def dump(payload: PayloadLike) -> bytes:
    return json.dumps(
        payload,
        check_circular=False,
        ensure_ascii=False,
        separators=(",", ":")).encode(ENCODING)


def content_length(line: bytes) -> Optional[int]:
    if line.startswith(b'Content-Length: '):
        _, value = line.split(b'Content-Length: ')
        value = value.strip()
        try:
            return int(value)
        except ValueError:
            raise ValueError("Invalid Content-Length header: {}".format(value))
    return None


class MessageType:
    error = 1
    warning = 2
    info = 3
    log = 4


class Session:

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._reader = reader
        self._writer = writer

        self._response_handlers: Dict[int, Tuple[Callable, Callable]]
        self._request_handlers: Dict[str,
                                     Callable[[PayloadLike], PayloadLike]] = {}
        self._notification_handlers: Dict[str,
                                          Callable[[PayloadLike], None]] = {}

        # initialize/shutdown/exit dance
        self._keep_going = True
        self._received_shutdown = False

        # properties used for testing purposes
        self._responses: Dict[str, PayloadLike] = {}
        self._received: Set[str] = set()
        self._received_cv = asyncio.Condition()

        self._install_handlers()

    def _log(self, message: str) -> None:
        self._notify("window/logMessage",
                     {"type": MessageType.info, "message": message})

    def _notify(self, method: str, params: PayloadLike) -> None:
        asyncio.create_task(self._send_payload(
            make_notification(method, params)))

    def _reply(self, request_id: int, params: PayloadLike) -> None:
        asyncio.create_task(self._send_payload(
            make_response(request_id, params)))

    def _error(self, request_id: int, err: Error) -> None:
        asyncio.create_task(self._send_payload(
            make_error_response(request_id, err)))

    async def _send_payload(self, payload: StringDict) -> None:
        body = dump(payload)
        content = (
            f"Content-Length: {len(body)}\r\n".encode(ENCODING),
            f"Content-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n".encode(
                ENCODING),
            body)
        self._writer.writelines(content)
        await self._writer.drain()

    async def _receive_payload(self, payload: StringDict) -> None:
        try:
            if "method" in payload:
                if "id" in payload:
                    await self._handle("request", payload, self._request_handlers, int(payload["id"]))
                else:
                    await self._handle("notification", payload, self._notification_handlers, None)
            elif "id" in payload:
                await self._response_handler(payload)
            else:
                self._log(f"Unknown payload type: {payload}")
        except Exception as err:
            self._log(f"Error handling server payload: {err}")

    async def _response_handler(self, response: StringDict) -> None:
        request_id = int(response["id"])
        handler, error_handler = self._response_handlers.pop(
            request_id, (None, None))
        assert handler
        if "result" in response and "error" not in response:
            if handler:
                await handler(response["result"])
            else:
                self._log(f"no response for request {request_id}")
        elif "result" not in response and "error" in response:
            error = response["error"]
            if error_handler:
                await error_handler(error)

    def _on_request(self, request_method: str, handler: Callable) -> None:
        self._request_handlers[request_method] = handler

    def _on_notification(self, notification_method: str, handler: Callable) -> None:
        self._notification_handlers[notification_method] = handler

    async def _handle(self, typestr: str, message: 'Dict[str, Any]', handlers: Dict[str, Callable],
                      request_id: Optional[int]) -> None:
        method = message.get("method", "")
        params = message.get("params")
        unhandled = True
        if not method.startswith("$test/"):
            async with self._received_cv:
                self._received.add(method)
                self._received_cv.notify_all()
                unhandled = False
        handler = handlers.get(method)
        if handler is None:
            if method in self._responses:
                assert request_id is not None
                self._reply(request_id, self._responses.pop(method))
            elif request_id is not None:
                self._error(request_id, Error(
                    ErrorCode.MethodNotFound, "method not found"))
            else:
                if unhandled:
                    self._log(f"unhandled {typestr} {method}")
        elif request_id is not None:
            # handle request
            try:
                self._reply(request_id, await handler(params))
            except Error as ex:
                self._error(request_id, ex)
            except Exception as ex:
                self._error(request_id, Error(
                    ErrorCode.InternalError, str(ex)))
        else:
            # handle notification
            asyncio.create_task(handler(params))

    def _handle_body(self, body: bytes) -> None:
        try:
            payload = json.loads(body)
            asyncio.create_task(self._receive_payload(payload))
        except IOError as ex:
            self._log(f"malformed {ENCODING}: {ex}")
        except UnicodeDecodeError as ex:
            self._log(f"malformed {ENCODING}: {ex}")
        except json.JSONDecodeError as ex:
            self._log(f"malformed JSON: {ex}")

    async def run_forever(self) -> bool:
        try:
            while self._keep_going and not self._reader.at_eof():
                line = await self._reader.readline()
                if not line:
                    continue
                try:
                    num_bytes = content_length(line)
                except ValueError:
                    continue
                if num_bytes is None:
                    continue
                while line and line.strip():
                    line = await self._reader.readline()
                if not line:
                    continue
                self._handle_body(await self._reader.readexactly(num_bytes))
        except (BrokenPipeError, ConnectionResetError):
            pass
        return self._received_shutdown

    def _install_handlers(self) -> None:
        self._on_request("initialize", self._initialize)
        self._on_request("shutdown", self._shutdown)
        self._on_notification("exit", self._on_exit)

        self._on_request("$test/getReceived", self._get_received)
        self._on_notification("$test/setResponse", self._on_set_response)

    async def _on_set_response(self, params: PayloadLike) -> None:
        if isinstance(params, dict):
            self._responses[params["method"]] = params["response"]

    async def _get_received(self, params: PayloadLike) -> PayloadLike:
        if not isinstance(params, dict):
            raise Error(ErrorCode.InvalidParams,
                        "expected params to be a dictionary")
        if "method" not in params:
            raise Error(ErrorCode.InvalidParams, 'expected "method" key')
        method = params["method"]
        if not isinstance(method, str):
            raise Error(ErrorCode.InvalidParams,
                        'expected "method" key to be a string')
        async with self._received_cv:
            while True:
                try:
                    self._received.remove(method)
                    return None
                except KeyError:
                    pass
                await self._received_cv.wait()

    async def _initialize(self, params: PayloadLike) -> PayloadLike:
        if not isinstance(params, dict):
            raise Error(ErrorCode.InvalidParams,
                        "expected params to be a dictionary")
        init_options = params.get("initializationOptions", {})
        if not isinstance(init_options, dict):
            raise Error(ErrorCode.InvalidParams,
                        "expected initializationOptions to be a dictionary")
        return init_options.get("serverResponse", {})

    async def _shutdown(self, _: PayloadLike) -> PayloadLike:
        self._received_shutdown = True
        return None

    async def _on_exit(self, _: PayloadLike) -> None:
        self._keep_going = False


# START: https://stackoverflow.com/a/52702646/990142
async def stdio(
    limit: int = asyncio.streams._DEFAULT_LIMIT
) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    loop = asyncio.get_running_loop()
    if sys.platform == 'win32':
        return _win32_stdio(loop)
    reader = asyncio.StreamReader(limit=limit)
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
    writer_transport, writer_protocol = await loop.connect_write_pipe(
        lambda: asyncio.streams.FlowControlMixin(),
        os.fdopen(sys.stdout.fileno(), 'wb'))
    writer = asyncio.streams.StreamWriter(
        writer_transport, writer_protocol, None, loop)
    return reader, writer


def _win32_stdio(loop: Optional[asyncio.AbstractEventLoop]) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:

    # no support for asyncio stdio yet on Windows, see https://bugs.python.org/issue26832
    # use an executor to read from stdio and write to stdout
    # note: if nothing ever drains the writer explicitly, no flushing ever takes place!
    class Win32StdinReader:

        def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
            self.loop = loop
            self.stdin = sys.stdin.buffer

        async def readline(self) -> None:
            # a single call to sys.stdin.readline() is thread-safe
            return await self.loop.run_in_executor(None, self.stdin.readline)

    class Win32StdoutWriter:

        def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
            self.loop = loop
            self.buffer: List[bytes] = []
            self.stdout = sys.stdout.buffer

        def write(self, data: bytes) -> None:
            self.buffer.append(data)

        async def drain(self) -> None:
            data, self.buffer = self.buffer, []
            # a single call to sys.stdout.writelines() is thread-safe
            return await self.loop.run_in_executor(None, sys.stdout.writelines, data)

    return Win32StdinReader(), Win32StdoutWriter()  # type: ignore
# END: https://stackoverflow.com/a/52702646/990142


async def main() -> bool:
    reader, writer = await stdio()
    session = Session(reader, writer)
    return await session.run_forever()


if __name__ == '__main__':
    parser = ArgumentParser(prog=__package__, description=__doc__)
    parser.add_argument("-v", "--version", action="store_true", help="print version and exit")
    args = parser.parse_args()
    if args.version:
        print(__package__, __version__)
        exit(0)
    else:
        try:
            exit(0 if asyncio.run(main()) else 1)
        except KeyboardInterrupt:
            exit(1)
