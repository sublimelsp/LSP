from __future__ import annotations

from .setup import IntegerNotZero
from .setup import make_stdio_test_config
from .setup import make_tcp_client_test_config
from .setup import make_tcp_server_test_config
from .setup import SublimeAioTestCase
from .test_session import MockLogger
from .test_session import MockManager
from LSP.plugin.api import LspPlugin
from LSP.plugin.api import OnTransportReadyContext
from LSP.plugin.core.protocol import Error
from LSP.plugin.core.sessions import Session
from typing import Any
from typing import Callable
from typing import TYPE_CHECKING
from typing_extensions import override
from unittest.mock import AsyncMock
from unittest.mock import patch
import asyncio
import sublime

if TYPE_CHECKING:
    from LSP.plugin.core.transports import Transport
    from LSP.plugin.core.types import ClientConfig


class HandshakePlugin(LspPlugin):
    hello = b""
    pong = b""

    @override
    async def on_transport_ready(self, context: OnTransportReadyContext) -> None:
        self.hello = await context.reader.readline()
        # Yield to the event loop before continuing. A JSON-RPC read loop that runs at the same time would now consume
        # the reply of the server.
        await asyncio.sleep(0.1)
        context.writer.write(b"ping\n")
        await context.writer.drain()
        self.pong = await context.reader.readline()


class StallingPlugin(LspPlugin):

    @override
    async def on_transport_ready(self, context: OnTransportReadyContext) -> None:
        # The server is not started with --handshake, so it never writes anything before JSON-RPC starts.
        await context.reader.readline()


class FailingPlugin(LspPlugin):

    @override
    async def on_transport_ready(self, context: OnTransportReadyContext) -> None:
        raise RuntimeError("handshake failed")


class TransportReadyTestCase(SublimeAioTestCase):

    @override
    async def setUp(self) -> None:
        self.manager = MockManager(sublime.active_window())
        self.transport: Transport | None = None
        self.factories = (make_stdio_test_config, make_tcp_client_test_config, make_tcp_server_test_config)

    @override
    async def tearDown(self) -> None:
        if self.transport:
            await self.transport.close()

    async def start(
        self, factory: Callable[[str, dict[str, Any]], ClientConfig], plugin_class: type[LspPlugin], handshake: bool
    ) -> tuple[Session, Transport]:
        config = factory("foo", {"serverResponse": {"capabilities": {}}})
        if handshake:
            config.command = [*config.command, "--handshake"]
        transport_config = config.create_transport_config()
        session = Session(self.manager, MockLogger(), [], config, plugin_class)
        self.transport = await transport_config.start(
            config.command, config.env, None, sublime.active_window().extract_variables(), session
        )
        return session, self.transport

    async def test_handshake_before_initialize(self) -> None:
        for factory in self.factories:
            with self.subTest(factory=factory):
                session, transport = await self.start(factory, HandshakePlugin, handshake=True)
                result = await session.initialize({}, None, transport)
                self.assertNotIsInstance(result, Error)
                plugin = session.plugin
                assert isinstance(plugin, HandshakePlugin)
                self.assertEqual(plugin.hello, b"hello\n")
                self.assertEqual(plugin.pong, b"pong\n")
                await session.end()
                self.assertEqual(await transport.close(), (0, None))

    async def test_timeout_closes_transport(self) -> None:
        for factory in self.factories:
            with self.subTest(factory=factory):
                session, transport = await self.start(factory, StallingPlugin, handshake=False)
                with patch('LSP.plugin.core.sessions.TRANSPORT_READY_TIMEOUT', 0.1), self.assertRaisesRegex(
                    TimeoutError, 'on_transport_ready did not finish'
                ):
                    await session.initialize({}, None, transport)
                self.assertIsNone(transport._process)

    async def test_exception_closes_transport(self) -> None:
        for factory in self.factories:
            with self.subTest(factory=factory), patch.object(self.manager, "on_post_exit", AsyncMock()):
                session, transport = await self.start(factory, FailingPlugin, handshake=False)
                with self.assertRaisesRegex(RuntimeError, 'handshake failed'):
                    await session.initialize({}, None, transport)
                self.assertIsNone(transport._process)
                self.assertTrue(session.end_requested)
                self.manager.on_post_exit.assert_awaited_once_with(session, IntegerNotZero(), None)  # pyright: ignore[reportAttributeAccessIssue]
