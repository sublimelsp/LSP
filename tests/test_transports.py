from __future__ import annotations

from .setup import make_stdio_test_config
from .setup import make_tcp_client_test_config
from .setup import make_tcp_server_test_config
from .setup import SublimeAioTestCase
from .setup import TextDocumentTestCase
from LSP.plugin.core.transports import LaunchConfig
from LSP.plugin.core.transports import TcpClientTransportConfig
from LSP.plugin.core.transports import Transport
from LSP.plugin.core.transports import TransportCallbacks
from LSP.plugin.core.types import ClientConfig
from typing import Any
from typing import TYPE_CHECKING
from typing_extensions import override
from unittest.mock import patch
import asyncio
import asyncio.subprocess
import sublime

if TYPE_CHECKING:
    from LSP.plugin.core.protocol import JSONRPCMessage


class ViewStatusTestCase(TextDocumentTestCase):
    statuses: list[str]

    @override
    @classmethod
    async def setUpClass(cls) -> None:
        with patch.object(ClientConfig, 'set_view_status', autospec=True) as set_view_status:
            await super().setUpClass()
        cls.statuses = [call.args[2] for call in set_view_status.call_args_list]


class StdioViewStatusTests(ViewStatusTestCase):

    def test_shows_starting_status(self) -> None:
        self.assertIn("starting...", self.statuses)
        self.assertNotIn("waiting for connection...", self.statuses)


class TcpClientViewStatusTests(ViewStatusTestCase):

    @override
    @classmethod
    def get_stdio_test_config(cls) -> ClientConfig:
        return make_tcp_server_test_config("TEST")

    def test_shows_waiting_for_connection_status(self) -> None:
        self.assertIn("waiting for connection...", self.statuses)
        self.assertNotIn("starting...", self.statuses)


class TcpServerViewStatusTests(ViewStatusTestCase):

    @override
    @classmethod
    def get_stdio_test_config(cls) -> ClientConfig:
        return make_tcp_client_test_config("TEST")

    def test_shows_waiting_for_connection_status(self) -> None:
        self.assertIn("waiting for connection...", self.statuses)
        self.assertNotIn("starting...", self.statuses)


class TcpClientConnectFailureTests(SublimeAioTestCase):

    async def _start_and_get_process(self, command: list[str]) -> asyncio.subprocess.Process:
        processes: list[asyncio.subprocess.Process] = []
        launch_start = LaunchConfig.start

        async def start(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
            processes.append(await launch_start(*args, **kwargs))
            return processes[-1]

        with patch('LSP.plugin.core.transports.TCP_CONNECT_TIMEOUT', 0.1), \
             patch.object(LaunchConfig, 'start', start), \
             self.assertRaisesRegex(RuntimeError, 'Failed to connect'):
            await TcpClientTransportConfig(None).start(command, None, None, {}, TransportCallbacks())
        return processes[0]

    async def test_kills_running_process(self) -> None:
        process = await self._start_and_get_process(['python3', '-c', 'import time; time.sleep(60)'])
        self.assertIsNotNone(process.returncode)
        self.assertNotEqual(process.returncode, 0)

    async def test_handles_already_exited_process(self) -> None:
        process = await self._start_and_get_process(['python3', '-c', ''])
        self.assertEqual(process.returncode, 0)


class Callbacks(TransportCallbacks):

    def __init__(self) -> None:
        super().__init__()
        self.responses: asyncio.Queue[JSONRPCMessage] = asyncio.Queue()
        self.exit_code: int | None = None
        self.exception: Exception | None = None
        self.stderr_messages: list[str] = []
        self.number_of_transport_close_callbacks = 0
        self.close_event = asyncio.Event()

    async def on_transport_close(self, exit_code: int, exception: Exception | None) -> None:
        self.exit_code = exit_code
        self.exception = exception
        self.number_of_transport_close_callbacks += 1
        self.close_event.set()

    async def on_payload(self, payload: JSONRPCMessage) -> None:
        self.responses.put_nowait(payload)

    def on_stderr_message(self, message: str) -> None:
        self.stderr_messages.append(message)


class TransportTestCase(SublimeAioTestCase):
    async def setUp(self) -> None:
        config = make_stdio_test_config("foo")
        transport_config = config.create_transport_config()
        launch = transport_config.resolve_launch_config(
            config.command, config.env, sublime.active_window().extract_variables()
        )
        self.callbacks = Callbacks()
        self.transport = await transport_config.start(launch.command, launch.env, None, {}, self.callbacks)

    async def tearDown(self) -> None:
        if (t := getattr(self, "transport", None)) and isinstance(t, Transport):
            await t.close()

    async def test_closing_a_never_started_transport(self) -> None:
        exit_code, exception = await self.transport.close()
        self.assertIsNone(exit_code)
        self.assertIsNone(self.transport._process)
        self.assertIsNone(exception)

    async def test_closing_prematurely(self) -> None:
        self.transport.start()
        exit_code, exception = await self.transport.close()
        # the fake server (tests/server.py) returns 1 when the shutdown request wasn't sent.
        self.assertEqual(exit_code, 1)
        self.assertIsNone(exception)

    async def test_closing_twice(self) -> None:
        self.transport.start()
        await self.transport.send({"jsonrpc": "2.0", "id": 1, "method": "shutdown"})
        await self.callbacks.responses.get()
        exit_code1, exception1 = await self.transport.close()
        self.assertEqual(self.callbacks.number_of_transport_close_callbacks, 1)
        self.assertEqual(exit_code1, 0)
        self.assertIsNone(exception1)
        exit_code2, exception2 = await self.transport.close()
        self.assertEqual(self.callbacks.number_of_transport_close_callbacks, 1)
        self.assertEqual(exit_code1, exit_code2)
        self.assertEqual(exception1, exception2)

    async def test_closing_properly(self) -> None:
        self.transport.start()
        await self.transport.send({"jsonrpc": "2.0", "id": 1, "method": "shutdown"})
        await self.transport.send({"jsonrpc": "2.0", "method": "exit"})
        await self.callbacks.responses.get()
        await self.callbacks.close_event.wait()
        self.assertEqual(self.callbacks.exit_code, 0)
        self.assertIsNone(self.callbacks.exception)
        self.assertEqual(self.callbacks.number_of_transport_close_callbacks, 1)

    async def test_closing_concurrently(self) -> None:
        self.transport.start()
        event = asyncio.Event()

        async def closer() -> None:
            await event.wait()
            await self.transport.close()

        closers = [closer() for _ in range(10)]
        closers_future = asyncio.gather(*closers)
        await asyncio.sleep(1)
        event.set()
        await closers_future
        self.assertEqual(self.callbacks.number_of_transport_close_callbacks, 1)
        self.assertIsNone(self.callbacks.exception)
        self.assertIsNotNone(self.callbacks.exit_code)

    async def test_process_dies_unexpectedly(self) -> None:
        self.transport.start()
        await asyncio.sleep(0.1)
        self.assertIsNotNone(self.transport._process)
        assert self.transport._process
        self.transport._process.kill()
        await self.callbacks.close_event.wait()
        self.assertEqual(self.callbacks.number_of_transport_close_callbacks, 1)
        self.assertIsNone(self.callbacks.exception)
        self.assertIsNotNone(self.callbacks.exit_code)
        self.assertNotEqual(self.callbacks.exit_code, 0)

    async def test_process_stops_with_nonzero_exit_code(self) -> None:
        self.transport.start()
        # the fake server returns 1 if the shutdown request wasn't received.
        # it will exit upon receiving the exit notification.
        await self.transport.send({"jsonrpc": "2.0", "method": "exit"})
        await self.callbacks.close_event.wait()
        self.assertEqual(self.callbacks.exit_code, 1)
        self.assertIsNone(self.callbacks.exception)
        self.assertEqual(self.callbacks.number_of_transport_close_callbacks, 1)
