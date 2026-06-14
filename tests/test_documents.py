from __future__ import annotations

from .setup import add_config
from .setup import close_test_view
from .setup import expand
from .setup import make_stdio_test_config
from .setup import make_tcp_client_test_config
from .setup import make_tcp_server_test_config
from .setup import remove_config
from .setup import SublimeAioTestCase
from LSP.plugin.core.open import open_file
from LSP.plugin.core.protocol import Request
from LSP.plugin.core.registry import windows
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.documents import DocumentSyncListener
from os.path import join
from sublime_plugin import view_event_listeners
from typing_extensions import override
import asyncio
import sublime


class WindowDocumentHandlerTests(SublimeAioTestCase):

    def ensure_document_listener_created(self) -> DocumentSyncListener | None:
        assert self.view
        # Bug in ST3? Either that, or CI runs with ST window not in focus and that makes ST3 not trigger some
        # events like on_load_async, on_activated, on_deactivated. That makes things not properly initialize on
        # opening file (manager missing in DocumentSyncListener)
        # Revisit this once we're on ST4.
        for listener in view_event_listeners[self.view.id()]:
            if isinstance(listener, DocumentSyncListener):
                return listener
        return None

    @override
    async def setUp(self) -> None:
        initialization_options = {
            "serverResponse": {
                "capabilities": {
                    "textDocumentSync": {
                        "openClose": True,
                        "change": 1,
                        "save": True
                    },
                }
            }
        }
        self.window = sublime.active_window()
        self.assertTrue(self.window)
        self.session1 = None
        self.session2 = None
        self.session3 = None
        self.config1 = make_stdio_test_config("TEST-1", initialization_options)
        self.config2 = make_tcp_client_test_config("TEST-2", initialization_options)
        self.config3 = make_tcp_server_test_config("TEST-3", initialization_options)
        self.wm = windows.lookup(self.window)
        self.assertIsNotNone(self.wm)
        assert self.wm
        add_config(self.config1)
        add_config(self.config2)
        add_config(self.config3)
        self.wm.get_config_manager().all[self.config1.name] = self.config1
        self.wm.get_config_manager().all[self.config2.name] = self.config2
        self.wm.get_config_manager().all[self.config3.name] = self.config3

    async def test_sends_did_open_to_multiple_sessions(self) -> None:
        filename = expand(join("$packages", "LSP", "tests", "testfile.txt"), self.window)
        await close_test_view(self.window.find_open_file(filename))
        self.view = await open_file(self.window, filename_to_uri(filename))
        self.assertIsNotNone(self.wm)
        assert self.wm
        assert self.view
        self.assertTrue(self.wm.get_config_manager().match_view(self.view, self.wm.workspace_folders))
        # self.init_view_settings()
        listener = self.ensure_document_listener_created()
        self.assertIsNotNone(listener)
        assert listener
        self.session1 = await self.wm.start(self.config1, listener)
        self.session2 = await self.wm.start(self.config2, listener)
        self.session3 = await self.wm.start(self.config3, listener)
        self.assertIsNotNone(self.session1)
        self.assertIsNotNone(self.session2)
        self.assertIsNotNone(self.session3)
        assert self.session1
        assert self.session2
        assert self.session3
        self.assertEqual(self.session1.config.name, self.config1.name)
        self.assertEqual(self.session2.config.name, self.config2.name)
        self.assertEqual(self.session3.config.name, self.config3.name)
        await self.assert_rpc_message("initialize")
        await self.assert_rpc_message("initialized")
        await self.assert_rpc_message("textDocument/didOpen")
        self.view.run_command("insert", {"characters": "a"})
        await self.assert_rpc_message("textDocument/didChange")
        await close_test_view(self.view)
        await self.assert_rpc_message("textDocument/didClose")

    @override
    async def tearDown(self) -> None:
        try:
            await close_test_view(self.view)
        except Exception:
            pass
        if self.session1:
            await self.session1.end()
        if self.session2:
            await self.session2.end()
        if self.session3:
            await self.session3.end()
        try:
            remove_config(self.config3)
        except ValueError:
            pass
        try:
            remove_config(self.config2)
        except ValueError:
            pass
        try:
            remove_config(self.config1)
        except ValueError:
            pass
        assert self.wm
        self.wm.get_config_manager().all.pop(self.config3.name, None)
        self.wm.get_config_manager().all.pop(self.config2.name, None)
        self.wm.get_config_manager().all.pop(self.config1.name, None)

    async def assert_rpc_message(self, method: str) -> None:
        assert self.session1
        assert self.session2
        assert self.session3
        timeout = 5
        await asyncio.wait_for(self.session1.request(Request("$test/getReceived", {"method": method})), timeout=timeout)
        await asyncio.wait_for(self.session2.request(Request("$test/getReceived", {"method": method})), timeout=timeout)
        await asyncio.wait_for(self.session3.request(Request("$test/getReceived", {"method": method})), timeout=timeout)
