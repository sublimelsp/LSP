from __future__ import annotations

from .async_test_case import AsyncTestCase
from .async_test_case import FutureLike
from .test_mocks import basic_responses
from LSP.plugin.core.aio import run_coroutine_threadsafe
from LSP.plugin.core.collections import DottedDict
from LSP.plugin.core.open import open_file
from LSP.plugin.core.protocol import Notification
from LSP.plugin.core.protocol import Request
from LSP.plugin.core.registry import windows
from LSP.plugin.core.settings import client_configs
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.types import ClientStates
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.documents import DocumentSyncListener
from os import environ
from os.path import join
from sublime_plugin import view_event_listeners
from typing import Any
from typing import Coroutine
from typing import TYPE_CHECKING
import asyncio
import sublime

if TYPE_CHECKING:
    from LSP.protocol import CodeAction
    from LSP.protocol import LSPAny

CI = any(key in environ for key in ("TRAVIS", "CI", "GITHUB_ACTIONS"))

TIMEOUT_TIME = 10000 if CI else 2000
text_config = ClientConfig(name="textls", selector="text.plain", command=[], tcp_port=None)


class YieldPromise:
    __slots__ = ("__done", "__result")

    def __init__(self) -> None:
        self.__done = False

    def __call__(self) -> bool:
        return self.__done

    def fulfill(self, result: Any = None) -> None:
        assert not self.__done
        self.__result = result
        self.__done = True

    def result(self) -> Any:
        return self.__result


def make_stdio_test_config(name: str, init_options: dict[str, Any] | None = None) -> ClientConfig:
    """Create a config for starting the fake language server in STDIO mode."""
    return ClientConfig(
        name=name,
        command=["python3", join("$packages", "LSP", "tests", "server.py")],
        selector="text.plain",
        initialization_options=DottedDict(init_options),
        enabled=True,
    )


def make_tcp_server_test_config(name: str, init_options: dict[str, Any] | None = None) -> ClientConfig:
    """
    Create a config for starting the fake server in TCP mode, and make it act as the TCP server, awaiting a single
    client connection.
    """
    return ClientConfig(
        name=name,
        command=["python3", join("$packages", "LSP", "tests", "server.py"), "--tcp-port", "$port", "--mode=server"],
        selector="text.plain",
        initialization_options=DottedDict(init_options),
        tcp_port=0,  # select a free one for me
        enabled=True,
    )


def make_tcp_client_test_config(name: str, init_options: dict[str, Any] | None = None) -> ClientConfig:
    """
    Create a config for starting the fake server in TCP mode, and make it act as the TCP client, where it connects to
    the LSP plugin.
    """
    return ClientConfig(
        name=name,
        command=["python3", join("$packages", "LSP", "tests", "server.py"), "--tcp-port", "$port", "--mode=client"],
        selector="text.plain",
        initialization_options=DottedDict(init_options),
        tcp_port=-1,  # select a free one for me
        enabled=True,
    )


def add_config(config: ClientConfig) -> None:
    client_configs.add_for_testing(config)


def remove_config(config: ClientConfig) -> None:
    client_configs.remove_for_testing(config)


async def close_test_view(view: sublime.View | None) -> None:
    if view:
        view.set_scratch(True)
        while view.is_loading():  # noqa: ASYNC110
            await asyncio.sleep(0.05)
        view.close()


def expand(s: str, w: sublime.Window) -> str:
    return sublime.expand_variables(s, w.extract_variables())


class SublimeAioTestCase(AsyncTestCase):
    timeout_ms = TIMEOUT_TIME

    @classmethod
    def run_coroutine(cls, coro: Coroutine) -> FutureLike:
        return run_coroutine_threadsafe(coro)

    async def ensure_document_listener_created(self) -> DocumentSyncListener | None:
        assert self.view
        # Bug in ST3? Either that, or CI runs with ST window not in focus and that makes ST3 not trigger some
        # events like on_load_async, on_activated, on_deactivated. That makes things not properly initialize on
        # opening file (manager missing in DocumentSyncListener)
        # Revisit this once we're on ST4.
        for listener in view_event_listeners[self.view.id()]:
            if isinstance(listener, DocumentSyncListener):
                return listener
        return None


class TextDocumentTestCase(SublimeAioTestCase):

    view: sublime.View

    @classmethod
    def get_stdio_test_config(cls) -> ClientConfig:
        return make_stdio_test_config("TEST")

    async def setUp(self) -> None:
        # BEGIN: TODO: Move to a setUpClass async method.
        test_name = self.get_test_name()
        server_capabilities = self.get_test_server_capabilities()
        window = sublime.active_window()
        filename = expand(join("$packages", "LSP", "tests", f"{test_name}.txt"), window)
        open_view = window.find_open_file(filename)
        await close_test_view(open_view)
        self.config = self.get_stdio_test_config()
        self.config.initialization_options.set("serverResponse", server_capabilities)
        add_config(self.config)
        self.wm = windows.lookup(window)
        self.view = await open_file(window, filename_to_uri(filename))  # type: ignore
        self.assertIsNotNone(self.view)
        assert self.view
        self.assertIsNotNone(self.wm)
        assert self.wm
        listener = await self.ensure_document_listener_created()
        self.assertIsNotNone(listener)
        assert listener
        self.session = await self.wm.start(self.config, listener)
        self.initialize_params = await self.await_message("initialize")
        await self.await_message("initialized")
        # await close_test_view(self.view)
        # END: TODO: Move to a setUpClass async method.

        # window = sublime.active_window()
        # filename = expand(join("$packages", "LSP", "tests", f"{self.get_test_name()}.txt"), window)
        # open_view = window.find_open_file(filename)
        # if not open_view:
        #     self.__class__.view = window.open_file(filename)
        #     yield {"condition": lambda: not self.view.is_loading(), "timeout": TIMEOUT_TIME}
        #     self.assertTrue(self.wm.get_config_manager().match_view(self.view, self.wm.workspace_folders))
        # self.init_view_settings()
        # yield self.ensure_document_listener_created
        params = await self.await_message("textDocument/didOpen")
        self.assertIsInstance(params, dict)
        assert isinstance(params, dict)
        self.assertEqual(params["textDocument"]["version"], 0)

    @classmethod
    def get_test_name(cls) -> str:
        return "testfile"

    @classmethod
    def get_test_server_capabilities(cls) -> dict:
        return basic_responses["initialize"]

    def init_view_settings(self) -> None:
        assert self.view
        s = self.view.settings().set
        s("auto_complete_selector", "text")
        s("ensure_newline_at_eof_on_save", False)
        s("rulers", [])
        s("tab_size", 4)
        s("translate_tabs_to_spaces", False)
        s("word_wrap", False)
        s("lsp_format_on_save", False)

    async def await_message(self, method: str) -> LSPAny:
        """
        Awaits until server receives a request with a specified method.

        If the server has already received a request with a specified method before, it will
        immediately return the response for that previous request. If it hasn't received such
        request yet, it will wait for it and then respond.

        :param      method: The method type that we are awaiting response for.

        :returns:   resolved value.
        """
        # cls.assertIsNotNone(cls.session)
        assert self.session
        return await self.session.request(Request("$test/getReceived", {"method": method}))

    async def make_server_do_fake_request(self, method: str, params: LSPAny) -> LSPAny:
        """Make the fake server do an arbitrary request."""
        assert self.session
        return await self.session.request(Request("$test/fakeRequest", {"method": method, "params": params}))

    async def await_run_code_action(self, code_action: CodeAction) -> LSPAny:
        assert self.session
        return await self.session.run_code_action(code_action, progress=False, view=self.view)

    async def mock_response(self, method: str, response: LSPAny) -> None:
        """Set up what the fake server should reply when it receives this method."""
        self.assertIsNotNone(self.session)
        assert self.session
        await self.session.notify(Notification("$test/setResponse", {"method": method, "response": response}))

    async def mock_responses(self, responses: list[tuple[str, LSPAny]]) -> None:
        """Set up what the fake server should reply, given these request methods."""
        self.assertIsNotNone(self.session)
        assert self.session
        payload = [{"method": method, "response": responses} for method, responses in responses]
        await self.session.request(Request("$test/setResponses", payload))

    async def mock_client_notification(self, method: str, params: LSPAny = None) -> LSPAny:
        """Emit an arbitrary notification from the fake server."""
        self.assertIsNotNone(self.session)
        assert self.session
        await self.session.request(Request("$test/sendNotification", {"method": method, "params": params}))
        return params

    async def await_clear_view_and_save(self) -> None:
        assert isinstance(self.view, sublime.View)
        self.view.run_command("select_all")
        self.view.run_command("left_delete")
        self.view.run_command("save")
        await self.await_message("textDocument/didChange")
        await self.await_message("textDocument/didSave")

    async def await_view_change(self, expected_change_count: int) -> None:
        assert isinstance(self.view, sublime.View)
        v = self.view
        while True:
            if v.change_count() == expected_change_count:
                return
            await asyncio.sleep(0.05)

    def insert_characters(self, characters: str) -> int:
        assert isinstance(self.view, sublime.View)
        self.view.run_command("insert", {"characters": characters})
        return self.view.change_count()

    async def tearDown(self) -> None:
        try:
            await close_test_view(self.view)
            if self.session:
                await self.session.end()
                self.session = None
            if self.wm and self.view:
                while self.wm.get_session(self.config.name, self.view.file_name()) is not None:  # noqa: ASYNC110
                    await asyncio.sleep(0.05)
                self.wm = None
        finally:
            # restore the user's configs
            remove_config(self.config)
