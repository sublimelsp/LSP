from __future__ import annotations

from .setup import make_stdio_test_config
from .setup import SublimeAioTestCase
from .test_session import MockLogger
from .test_session import MockManager
from LSP.plugin.api import LspPlugin
from LSP.plugin.core.protocol import Error
from LSP.plugin.core.sessions import Session
from typing import TYPE_CHECKING
from typing_extensions import override
from unittest.mock import patch
import asyncio
import sublime

if TYPE_CHECKING:
    from LSP.plugin.core.transports import Transport


class HandshakePlugin(LspPlugin):
    hello = b""
    pong = b""

    @override
    async def on_transport_ready(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.hello = await reader.readline()
        # Yield to the event loop before continuing. A JSON-RPC read loop that runs at the same time would now consume
        # the reply of the server.
        await asyncio.sleep(0.1)
        writer.write(b"ping\n")
        await writer.drain()
        self.pong = await reader.readline()


class StallingPlugin(LspPlugin):

    @override
    async def on_transport_ready(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        # The server is not started with --handshake, so it never writes anything before JSON-RPC starts.
        await reader.readline()


class FailingPlugin(LspPlugin):

    @override
    async def on_transport_ready(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        raise RuntimeError("handshake failed")


class TransportReadyTestCase(SublimeAioTestCase):

    @override
    async def setUp(self) -> None:
        self.manager = MockManager(sublime.active_window())
        self.transport: Transport | None = None

    @override
    async def tearDown(self) -> None:
        if self.transport:
            await self.transport.close()

    async def start(self, plugin_class: type[LspPlugin], handshake: bool) -> tuple[Session, Transport]:
        config = make_stdio_test_config("foo", {"serverResponse": {"capabilities": {}}})
        if handshake:
            config.command = [*config.command, "--handshake"]
        transport_config = config.create_transport_config()
        launch = transport_config.resolve_launch_config(
            config.command, config.env, sublime.active_window().extract_variables()
        )
        session = Session(self.manager, MockLogger(), [], config, plugin_class)
        self.transport = await transport_config.start(launch.command, launch.env, None, {}, session)
        return session, self.transport

    async def test_handshake_before_initialize(self) -> None:
        session, transport = await self.start(HandshakePlugin, handshake=True)
        result = await session.initialize({}, None, transport)
        self.assertNotIsInstance(result, Error)
        plugin = session.plugin
        assert isinstance(plugin, HandshakePlugin)
        self.assertEqual(plugin.hello, b"hello\n")
        self.assertEqual(plugin.pong, b"pong\n")
        await session.end()
        self.assertEqual(await transport.close(), (0, None))

    async def test_timeout_closes_transport(self) -> None:
        session, transport = await self.start(StallingPlugin, handshake=False)
        with patch('LSP.plugin.core.sessions.TRANSPORT_READY_TIMEOUT', 0.1), self.assertRaises(TimeoutError):
            await session.initialize({}, None, transport)
        self.assertIsNone(transport._process)

    async def test_exception_closes_transport(self) -> None:
        session, transport = await self.start(FailingPlugin, handshake=False)
        with self.assertRaisesRegex(RuntimeError, 'handshake failed'):
            await session.initialize({}, None, transport)
        self.assertIsNone(transport._process)
