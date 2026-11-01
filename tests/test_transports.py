from __future__ import annotations

from .setup import make_tcp_client_test_config
from .setup import make_tcp_server_test_config
from .setup import SublimeAioTestCase
from .setup import TextDocumentTestCase
from LSP.plugin.core.transports import LaunchConfig
from LSP.plugin.core.transports import TcpClientTransportConfig
from LSP.plugin.core.transports import TransportCallbacks
from LSP.plugin.core.types import ClientConfig
from typing import Any
from typing import TYPE_CHECKING
from typing_extensions import override
from unittest.mock import patch

if TYPE_CHECKING:
    import asyncio.subprocess


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
