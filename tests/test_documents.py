from __future__ import annotations

from LSP.plugin.core.logging import debug
from LSP.plugin.core.protocol import Request
from LSP.plugin.core.registry import windows
from LSP.plugin.core.types import ClientStates
from LSP.plugin.documents import DocumentSyncListener
from os.path import join
from setup import add_config
from setup import close_test_view
from setup import expand
from setup import make_stdio_test_config
from setup import remove_config
from setup import TIMEOUT_TIME
from setup import YieldPromise
from sublime_plugin import view_event_listeners
from typing import Any
from typing import Generator
from unittesting import DeferrableTestCase
import sublime


class WindowDocumentHandlerTests(DeferrableTestCase):

    def ensure_document_listener_created(self) -> bool:
        assert self.view
        # Bug in ST3? Either that, or CI runs with ST window not in focus and that makes ST3 not trigger some
        # events like on_load_async, on_activated, on_deactivated. That makes things not properly initialize on
        # opening file (manager missing in DocumentSyncListener)
        # Revisit this once we're on ST4.
        for listener in view_event_listeners[self.view.id()]:
            if isinstance(listener, DocumentSyncListener):
                sublime.set_timeout_async(listener.on_activated_async)
                return True
        return False

    def setUp(self) -> Generator:
        init_options = {
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
        self.config1 = make_stdio_test_config()
        self.config1.init_options.assign(init_options)
        self.config2 = make_stdio_test_config()
        self.config2.init_options.assign(init_options)
        self.config2.name = "TEST-2"
        self.config2.status_key = "lsp_TEST-2"
        self.wm = windows.lookup(self.window)
        add_config(self.config1)
        add_config(self.config2)
        self.wm.get_config_manager().all[self.config1.name] = self.config1
        self.wm.get_config_manager().all[self.config2.name] = self.config2

    def test_sends_did_open_to_multiple_sessions(self) -> Generator:
        filename = expand(join("$packages", "LSP", "tests", "testfile.txt"), self.window)
        open_view = self.window.find_open_file(filename)
        yield from close_test_view(open_view)
        self.view = self.window.open_file(filename)
        yield {"condition": lambda: not self.view.is_loading(), "timeout": TIMEOUT_TIME}
        self.assertTrue(self.wm.get_config_manager().match_view(self.view))
        # self.init_view_settings()
        yield {"condition": self.ensure_document_listener_created, "timeout": TIMEOUT_TIME}
        yield {
            "condition": lambda: self.wm.get_session(self.config1.name, self.view.file_name()) is not None,
            "timeout": TIMEOUT_TIME}
        yield {
            "condition": lambda: self.wm.get_session(self.config2.name, self.view.file_name()) is not None,
            "timeout": TIMEOUT_TIME}
        self.session1 = self.wm.get_session(self.config1.name, self.view.file_name())
        self.session2 = self.wm.get_session(self.config2.name, self.view.file_name())
        self.assertIsNotNone(self.session1)
        self.assertIsNotNone(self.session2)
        self.assertEqual(self.session1.config.name, self.config1.name)
        self.assertEqual(self.session2.config.name, self.config2.name)
        yield {"condition": lambda: self.session1.state == ClientStates.READY, "timeout": TIMEOUT_TIME}
        yield {"condition": lambda: self.session2.state == ClientStates.READY, "timeout": TIMEOUT_TIME}
        yield from self.await_message("initialize")
        yield from self.await_message("initialized")
        yield from self.await_message("textDocument/didOpen")
        self.view.run_command("insert", {"characters": "a"})
        yield from self.await_message("textDocument/didChange")
        self.assertEqual(self.view.get_status("lsp_TEST"), "TEST")
        self.assertEqual(self.view.get_status("lsp_TEST-2"), "TEST-2")
        yield from close_test_view(self.view)
        yield from self.await_message("textDocument/didClose")

    def doCleanups(self) -> Generator:
        try:
            yield from close_test_view(self.view)
        except Exception:
            pass
        if self.session1:
            sublime.set_timeout_async(self.session1.end_async)
            yield lambda: self.session1.state == ClientStates.STOPPING
        if self.session2:
            sublime.set_timeout_async(self.session2.end_async)
            yield lambda: self.session2.state == ClientStates.STOPPING
        try:
            remove_config(self.config2)
        except ValueError:
            pass
        try:
            remove_config(self.config1)
        except ValueError:
            pass
        self.wm.get_config_manager().all.pop(self.config2.name, None)
        self.wm.get_config_manager().all.pop(self.config1.name, None)
        yield from super().doCleanups()

    def await_message(self, method: str) -> Generator:
        promise1 = YieldPromise()
        promise2 = YieldPromise()

        def handler1(params: Any) -> None:
            promise1.fulfill(params)

        def handler2(params: Any) -> None:
            promise2.fulfill(params)

        def error_handler(params: Any) -> None:
            debug("Got error:", params, "awaiting timeout :(")

        self.session1.send_request(Request("$test/getReceived", {"method": method}), handler1, error_handler)
        self.session2.send_request(Request("$test/getReceived", {"method": method}), handler2, error_handler)
        yield {"condition": promise1, "timeout": TIMEOUT_TIME}
        yield {"condition": promise2, "timeout": TIMEOUT_TIME}
