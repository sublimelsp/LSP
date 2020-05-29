"""
A simple test server for integration tests.

Only understands stdio.
Uses the asyncio module and mypy types, so you'll need a modern Python.

To make this server reply to requests, send the $test/setResponse notification.

To make this server do a request, send the $test/fakeRequest request.

To await a method that this server should eventually (or already has) received,
send the $test/getReceived request. If the method was already received, it will
return None immediately. Otherwise, it will wait for the method. You should
have a timeout in your tests to ensure your tests won't hang forever.

To make server send out a notification, send the $test/sendNotification request
with expected notification method in params['method'] and params in params['params'].
Tests can await this request to make sure that they receive notification before code
resumes (since response to request will arrive after requested notification).

TODO: Untested on Windows.
"""
from argparse import ArgumentParser
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, Iterable, Awaitable
import asyncio
import json
import os
import sys
import uuid


__package__ = "server"
__version__ = "1.0.0"


if sys.version_info[0] < 3:
    print("only works for python3.6 and higher")
    exit(1)
if sys.version_info[1] < 6:
    print("only works for python3.6 and higher")
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

    @classmethod
    def from_lsp(cls, d: StringDict) -> 'Error':
        return Error(d["code"], d["message"])

    def __str__(self) -> str:
        return f"{super().__str__()} ({self.code})"


def jsonrpc() -> StringDict:
    return {"jsonrpc": "2.0"}


def make_response(request_id: Any, params: PayloadLike) -> StringDict:
    return {**jsonrpc(), "id": request_id, "result": params}


def make_error_response(request_id: Any, err: Error) -> StringDict:
    return {**jsonrpc(), "id": request_id, "error": err.to_lsp()}


def make_notification(method: str, params: PayloadLike) -> StringDict:
    return {**jsonrpc(), "method": method, "params": params}


def make_request(method: str, request_id: Any, params: PayloadLike) -> StringDict:
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


class StopLoopException(Exception):
    pass


class Request:

    async def on_error(self, err: Error) -> None:
        pass

    async def on_result(self, params: PayloadLike) -> None:
        pass


class SimpleRequest(Request):

    def __init__(self) -> None:
        self.cv = asyncio.Condition()
        self.result = None  # type: PayloadLike
        self.error = None  # type: Optional[Error]

    async def on_result(self, params: PayloadLike) -> None:
        self.result = params
        async with self.cv:
            self.cv.notify()

    async def on_error(self, err: Error) -> None:
        self.error = err
        async with self.cv:
            self.cv.notify()


class Session:

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._reader = reader
        self._writer = writer

        self._response_handlers: Dict[Any, Request] = {}
        self._request_handlers: Dict[str, Callable[[PayloadLike], Awaitable[PayloadLike]]] = {}
        self._notification_handlers: Dict[str, Callable[[PayloadLike], Awaitable[None]]] = {}

        # initialize/shutdown/exit dance
        self._received_shutdown = False

        # properties used for testing purposes
        self._responses: Dict[str, PayloadLike] = {}
        self._received: Dict[str, PayloadLike] = {}
        self._received_cv = asyncio.Condition()

        self._install_handlers()

    def _log(self, message: str) -> None:
        self._notify("window/logMessage",
                     {"type": MessageType.info, "message": message})

    def _notify(self, method: str, params: PayloadLike) -> None:
        asyncio.get_event_loop().create_task(self._send_payload(
            make_notification(method, params)))

    def _reply(self, request_id: Any, params: PayloadLike) -> None:
        asyncio.get_event_loop().create_task(self._send_payload(
            make_response(request_id, params)))

    def _error(self, request_id: Any, err: Error) -> None:
        asyncio.get_event_loop().create_task(self._send_payload(
            make_error_response(request_id, err)))

    async def request(self, method: str, params: PayloadLike) -> PayloadLike:
        request = SimpleRequest()
        request_id = str(uuid.uuid4())
        self._response_handlers[request_id] = request
        async with request.cv:
            await self._send_payload(make_request(method, request_id, params))
            await request.cv.wait()
        if isinstance(request.error, Error):
            raise request.error
        return request.result

    async def _send_payload(self, payload: StringDict) -> None:
        body = dump(payload)
        content = (
            f"Content-Length: {len(body)}\r\n".encode(ENCODING),
            f"Content-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n".encode(ENCODING),
            body)
        self._writer.writelines(content)
        await self._writer.drain()

    async def _receive_payload(self, payload: StringDict) -> None:
        try:
            if "method" in payload:
                if "id" in payload:
                    await self._handle("request", payload, self._request_handlers, payload["id"])
                else:
                    await self._handle("notification", payload, self._notification_handlers, None)
            elif "id" in payload:
                await self._response_handler(payload)
            else:
                self._log(f"Unknown payload type: {payload}")
        except Exception as err:
            self._log(f"Error handling server payload: {err}")

    async def _response_handler(self, response: StringDict) -> None:
        request = self._response_handlers.pop(response["id"])
        if "result" in response and "error" not in response:
            await request.on_result(response["result"])
        elif "result" not in response and "error" in response:
            await request.on_error(Error.from_lsp(response["error"]))
        else:
            await request.on_error(Error(ErrorCode.InvalidRequest, ''))

    def _on_request(self, request_method: str, handler: Callable[[PayloadLike], Awaitable[PayloadLike]]) -> None:
        self._request_handlers[request_method] = handler

    def _on_notification(self, notification_method: str, handler: Callable[[PayloadLike], Awaitable[None]]) -> None:
        self._notification_handlers[notification_method] = handler

    async def _handle(self, typestr: str, message: Dict[str, Any], handlers: Dict[str, Callable],
                      request_id: Optional[int]) -> None:
        method = message.get("method", "")
        params = message.get("params")
        unhandled = True
        if not method.startswith("$test/"):
            self._received[method] = params
            async with self._received_cv:
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
                self._error(request_id, Error(ErrorCode.InternalError, str(ex)))
        else:
            # handle notification
            try:
                await handler(params)
            except asyncio.CancelledError:
                return
            except Exception as ex:
                if not self._received_shutdown:
                    self._notify("window/logMessage", {"type": MessageType.error, "message": str(ex)})

    async def _handle_body(self, body: bytes) -> None:
        try:
            await self._receive_payload(json.loads(body))
        except IOError as ex:
            self._log(f"malformed {ENCODING}: {ex}")
        except UnicodeDecodeError as ex:
            self._log(f"malformed {ENCODING}: {ex}")
        except json.JSONDecodeError as ex:
            self._log(f"malformed JSON: {ex}")

    async def run_forever(self) -> bool:
        try:
            while not self._reader.at_eof():
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
                body = await self._reader.readexactly(num_bytes)
                asyncio.get_event_loop().create_task(self._handle_body(body))
        except (BrokenPipeError, ConnectionResetError, StopLoopException):
            pass
        return self._received_shutdown

    def _install_handlers(self) -> None:
        self._on_request("initialize", self._initialize)
        self._on_request("shutdown", self._shutdown)
        self._on_notification("exit", self._on_exit)

        self._on_request("$test/getReceived", self._get_received)
        self._on_request("$test/fakeRequest", self._fake_request)
        self._on_request("$test/sendNotification", self._send_notification)
        self._on_notification("$test/setResponse", self._on_set_response)

    async def _on_set_response(self, params: PayloadLike) -> None:
        if isinstance(params, dict):
            self._responses[params["method"]] = params["response"]

    async def _send_notification(self, params: PayloadLike) -> PayloadLike:
        method, payload = self._validate_request_params(params)
        self._notify(method, payload)
        return None

    async def _get_received(self, params: PayloadLike) -> PayloadLike:
        method, payload = self._validate_request_params(params)
        async with self._received_cv:
            while True:
                try:
                    return self._received.pop(method)
                except KeyError:
                    pass
                await self._received_cv.wait()

    async def _fake_request(self, params: PayloadLike) -> PayloadLike:
        method, payload = self._validate_request_params(params)
        return await self.request(method, payload)

    def _validate_request_params(self, params: PayloadLike) -> Tuple[str, Optional[Union[Dict, List]]]:
        if not isinstance(params, dict):
            raise Error(ErrorCode.InvalidParams, "expected params to be a dictionary")
        if "method" not in params:
            raise Error(ErrorCode.InvalidParams, 'expected "method" key')
        if not isinstance(params["method"], str):
            raise Error(ErrorCode.InvalidParams, 'expected "method" key to be a string')
        return (params["method"], params.get('params'))

    async def _initialize(self, params: PayloadLike) -> PayloadLike:
        if not isinstance(params, dict):
            raise Error(ErrorCode.InvalidParams,
                        "expected params to be a dictionary")
        init_options = params.get("initializationOptions", {})
        if not isinstance(init_options, dict):
            raise Error(ErrorCode.InvalidParams,
                        "expected initializationOptions to be a dictionary")
        return init_options.get("serverResponse", {})

    async def _shutdown(self, params: PayloadLike) -> PayloadLike:
        if params is not None:
            raise Error(ErrorCode.InvalidParams, "expected shutdown params to be null")
        self._received_shutdown = True
        return None

    async def _on_exit(self, params: PayloadLike) -> None:
        if params is not None:
            raise Error(ErrorCode.InvalidParams, "expected exit params to be null")
        self._reader.set_exception(StopLoopException())


# START: https://stackoverflow.com/a/52702646/990142
async def stdio() -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    loop = asyncio.get_event_loop()
    if sys.platform == 'win32':
        return _win32_stdio(loop)
    else:
        return await _unix_stdio(loop)


async def _unix_stdio(loop: asyncio.AbstractEventLoop) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    reader = asyncio.StreamReader(loop=loop)

    def reader_factory() -> asyncio.StreamReaderProtocol:
        return asyncio.StreamReaderProtocol(reader)

    def writer_factory() -> asyncio.streams.FlowControlMixin:
        return asyncio.streams.FlowControlMixin()

    await loop.connect_read_pipe(reader_factory, sys.stdin)
    pipe = os.fdopen(sys.stdout.fileno(), 'wb')
    writer_transport, writer_protocol = await loop.connect_write_pipe(writer_factory, pipe)
    writer = asyncio.streams.StreamWriter(writer_transport, writer_protocol, None, loop)
    return reader, writer


def _win32_stdio(loop: asyncio.AbstractEventLoop) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:

    # no support for asyncio stdio yet on Windows, see https://bugs.python.org/issue26832
    # use an executor to read from stdin and write to stdout
    # note: if nothing ever drains the writer explicitly, no flushing ever takes place!
    class Reader:

        def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
            self.loop = loop
            self.stdin = sys.stdin.buffer
            self.__exception: Optional[Exception] = None

        def at_eof(self) -> bool:
            return self.__exception is not None

        def set_exception(self, exception: Exception) -> None:
            self.__exception = exception

        def __check(self) -> None:
            if self.__exception is not None:
                raise self.__exception

        async def readline(self) -> bytes:
            self.__check()
            # a single call to sys.stdin.readline() is thread-safe
            return await self.loop.run_in_executor(None, self.stdin.readline)

        async def readexactly(self, n: int) -> bytes:
            self.__check()
            return await self.loop.run_in_executor(None, self.stdin.read, n)

    class Writer:

        def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
            self.loop = loop
            self.buffer: List[bytes] = []
            self.stdout = sys.stdout.buffer

        def write(self, data: bytes) -> None:
            self.buffer.append(data)

        def writelines(self, lines: Iterable[bytes]) -> None:
            self.buffer.extend(lines)

        async def drain(self) -> None:
            data, self.buffer = self.buffer, []

            def do_blocking_drain() -> None:
                self.stdout.write(b''.join(data))
                self.stdout.flush()

            await self.loop.run_in_executor(None, do_blocking_drain)

    return Reader(loop), Writer(loop)  # type: ignore
# END: https://stackoverflow.com/a/52702646/990142


async def main(tcp_port: Optional[int] = None) -> bool:
    if tcp_port is not None:

        class ClientConnectedCallback:

            def __init__(self) -> None:
                self.received_shutdown = False

            async def __call__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                session = Session(reader, writer)
                self.received_shutdown = await session.run_forever()

        callback = ClientConnectedCallback()
        server = await asyncio.start_server(callback, port=tcp_port)
        # NOTE: This is deliberately wrong -- we should stop serving once the exit notification is received.
        # But, it's good to have this botched logic here to make sure that servers shutdown in the integration tests.
        await server.serve_forever()
        return callback.received_shutdown
    else:
        reader, writer = await stdio()
        session = Session(reader, writer)
        return await session.run_forever()


if __name__ == '__main__':
    parser = ArgumentParser(prog=__package__, description=__doc__)
    parser.add_argument("-v", "--version", action="store_true", help="print version and exit")
    parser.add_argument("-p", "--tcp-port", type=int)
    args = parser.parse_args()
    if args.version:
        print(__package__, __version__)
        exit(0)
    loop = asyncio.get_event_loop()
    shutdown_received = False
    try:
        shutdown_received = loop.run_until_complete(main(args.tcp_port))
    except KeyboardInterrupt:
        pass
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()
    exit(0 if shutdown_received else 1)
