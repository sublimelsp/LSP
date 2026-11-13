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
import copy
import sublime
import time
import types

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
        # Deliberate long sleep to assert that payload handlers are stopped when the transport closes.
        await asyncio.sleep(5)

    def on_stderr_message(self, message: str) -> None:
        self.stderr_messages.append(message)


class TransportTestCaseBase(SublimeAioTestCase):
    def extra_server_command_args(self) -> list[str] | None:
        return None

    async def setUp(self) -> None:
        config = make_stdio_test_config("foo")
        if extra_args := self.extra_server_command_args():
            new_command = copy.deepcopy(config.command)
            new_command.extend(extra_args)
            config.command = new_command
        transport_config = config.create_transport_config()
        launch = transport_config.resolve_launch_config(
            config.command, config.env, sublime.active_window().extract_variables()
        )
        self.callbacks = Callbacks()
        self.transport = await transport_config.start(launch.command, launch.env, None, {}, self.callbacks)

    async def tearDown(self) -> None:
        if (t := getattr(self, "transport", None)) and isinstance(t, Transport):
            await t.close()


class TransportTestCase(TransportTestCaseBase):

    async def test_closing_a_never_started_transport(self) -> None:
        exit_code, exception = await self.transport.close()
        self.assertIsNotNone(exit_code)
        self.assertNotEqual(exit_code, 0)
        self.assertIsNone(self.transport._process)
        self.assertIsNone(exception)
        # The transport never ran, so there is nothing to report.
        await asyncio.sleep(0.1)
        self.assertEqual(self.callbacks.number_of_transport_close_callbacks, 0)

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
        await self.callbacks.close_event.wait()
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
        await asyncio.sleep(0.1)
        event.set()
        await closers_future
        await self.callbacks.close_event.wait()
        self.assertEqual(self.callbacks.number_of_transport_close_callbacks, 1)
        self.assertIsNone(self.callbacks.exception)
        # the fake server returns 1 when the shutdown request wasn't sent.
        self.assertEqual(self.callbacks.exit_code, 1)

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

    async def test_all_tasks_in_container_are_stopped(self) -> None:
        self.transport.start()
        # sending shutdown causes a JSON-RPC reply, which Transport._read_loop dispatches as a task.
        # That task takes 5 seconds (see Callbacks.on_payload).
        await self.transport.send({"jsonrpc": "2.0", "id": 1, "method": "shutdown"})
        while len(self.transport._tasks) != 1:  # ruff: ignore[async-busy-wait]
            await asyncio.sleep(0.05)
        # Now send the exit notification. That causes Transport._read_loop to exit its loop and clean up resources.
        await self.transport.send({"jsonrpc": "2.0", "method": "exit"})
        await self.callbacks.close_event.wait()
        # The transport is closed, so there should be no more tasks running.
        self.assertTrue(self.transport._task and self.transport._task.done())
        self.assertEqual(len(self.transport._tasks), 0)

    async def test_calling_close_from_inside_on_transport_closed_callback(self) -> None:
        transport = self.transport

        async def bad_on_transport_close_handler(self: Callbacks, exit_code: int, exception: Exception | None) -> None:
            self.exit_code = exit_code
            self.exception = exception
            self.number_of_transport_close_callbacks += 1
            await transport.close()
            self.close_event.set()

        bad_method = types.MethodType(bad_on_transport_close_handler, self.callbacks)
        with patch.object(self.callbacks, "on_transport_close", bad_method):
            self.transport.start()
            await self.transport.send({"jsonrpc": "2.0", "id": 1, "method": "shutdown"})
            await self.transport.send({"jsonrpc": "2.0", "method": "exit"})
            await self.callbacks.close_event.wait()
        self.assertEqual(self.callbacks.exit_code, 0)
        self.assertIsNone(self.callbacks.exception)
        self.assertEqual(self.callbacks.number_of_transport_close_callbacks, 1)

    async def test_closing_inside_payload_handler_cancels_the_handler(self) -> None:
        transport = self.transport
        handler_was_cancelled = False
        received_payload: JSONRPCMessage | None = None

        async def closing_on_payload_handler(payload: JSONRPCMessage) -> None:
            nonlocal received_payload
            received_payload = payload
            try:
                await transport.close()
            except asyncio.CancelledError:
                # The teardown cancels all payload handlers, including this one.
                nonlocal handler_was_cancelled
                handler_was_cancelled = True
                raise

        with patch.object(self.callbacks, "on_payload", closing_on_payload_handler):
            self.transport.start()
            await self.transport.send({"jsonrpc": "2.0", "id": 1, "method": "shutdown"})
            await self.callbacks.close_event.wait()
        self.assertTrue(handler_was_cancelled)
        self.assertEqual(received_payload, {"jsonrpc": "2.0", "id": 1, "result": None})
        self.assertEqual(self.callbacks.exit_code, 0)
        self.assertIsNone(self.callbacks.exception)
        self.assertEqual(self.callbacks.number_of_transport_close_callbacks, 1)


class TransportWithSlowProcessShutdownTestCase(TransportTestCaseBase):
    @override
    def extra_server_command_args(self) -> list[str] | None:
        return ["--sleep-ms-after-exit", "3000"]

    async def test_cancelled_close_still_releases_resources(self) -> None:
        self.transport.start()
        await self.transport.send({"jsonrpc": "2.0", "method": "exit"})
        # The fake server would take 3 seconds to exit. Kill it after 1 second instead, to stay within the test timeout.
        with patch('LSP.plugin.core.transports.PROCESS_SHUTDOWN_TIMEOUT', 1.0):
            close_task = asyncio.create_task(self.transport.close())
            # Sleep for 500ms, to let the fake server enter the asyncio.sleep, and to let the close() coroutine wait
            # for the process to finish.
            await asyncio.sleep(0.5)
        # We should be awaiting the graceful process shutdown at this point. The fake server is sleeping for 500ms
        # (and would still keep sleeping for another 2500ms).
        # Now pretend something cancels the close() coroutine.
        self.assertFalse(close_task.done())
        close_task.cancel()
        # The cancellation reaches the caller right away.
        with self.assertRaises(asyncio.CancelledError):
            await close_task
        # Regardless of cancellation of the close() coroutine, the teardown still runs to completion.
        await self.callbacks.close_event.wait()
        self.assertNotEqual(self.callbacks.exit_code, 0)  # killed by the shutdown timeout
        self.assertIsNone(self.transport._process)
        self.assertEqual(self.callbacks.number_of_transport_close_callbacks, 1)
        self.assertEqual(len(self.transport._tasks), 0)
        self.assertTrue(self.transport._task is not None and self.transport._task.done())

    async def test_process_is_killed_after_graceful_wait(self) -> None:
        self.transport.start()
        # send shutdown, so that the fake server would exit with status 0.
        await self.transport.send({"jsonrpc": "2.0", "id": 1, "method": "shutdown"})
        await self.transport.send({"jsonrpc": "2.0", "method": "exit"})
        start = time.monotonic()
        with patch('LSP.plugin.core.transports.PROCESS_SHUTDOWN_TIMEOUT', 0.1):
            exit_code, exception = await self.transport.close()
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 1.0)
        self.assertIsNotNone(exit_code)
        self.assertNotEqual(exit_code, 0)  # should have been killed, so status should not be 0
        self.assertIsNone(exception)
        self.assertIsNone(self.transport._process)
        await self.callbacks.close_event.wait()
        self.assertEqual(self.callbacks.number_of_transport_close_callbacks, 1)
