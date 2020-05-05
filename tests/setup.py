from LSP.plugin.core.documents import DocumentSyncListener
from LSP.plugin.core.logging import debug
from LSP.plugin.core.protocol import Notification, Request, WorkspaceFolder
from LSP.plugin.core.registry import windows
from LSP.plugin.core.sessions import Session
from LSP.plugin.core.settings import client_configs
from LSP.plugin.core.types import ClientConfig, LanguageConfig, ClientStates
from LSP.plugin.core.typing import Any, Optional, Generator
from os import environ
from os.path import dirname
from os.path import join
from sublime_plugin import view_event_listeners
from test_mocks import basic_responses
from unittesting import DeferrableTestCase
import sublime


CI = any(key in environ for key in ("TRAVIS", "CI", "GITHUB_ACTIONS"))

project_path = dirname(__file__)
test_file_path = join(project_path, "testfile.txt")
workspace_folders = [WorkspaceFolder.from_path(project_path)]
TIMEOUT_TIME = 10000 if CI else 2000
SUPPORTED_SCOPE = "text.plain"
SUPPORTED_SYNTAX = "Packages/Text/Plain text.tmLanguage"
text_language = LanguageConfig("text", [SUPPORTED_SCOPE], [SUPPORTED_SYNTAX])
text_config = ClientConfig("textls", [], None, languages=[text_language])


class YieldPromise:

    __slots__ = ('__done', '__result')

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


def make_stdio_test_config() -> ClientConfig:
    return ClientConfig(
        name="TEST",
        binary_args=["python3", join("$packages", "LSP", "tests", "server.py")],
        tcp_port=None,
        languages=[LanguageConfig(
            language_id="txt",
            scopes=[SUPPORTED_SCOPE],
            syntaxes=[SUPPORTED_SYNTAX])],
        enabled=True)


def add_config(config):
    client_configs.all.append(config)


def remove_config(config):
    client_configs.all.remove(config)


def close_test_view(view: sublime.View):
    if view:
        view.set_scratch(True)
        view.close()


def expand(s: str, w: sublime.Window) -> str:
    return sublime.expand_variables(s, w.extract_variables())


class SessionType:
    Stdio = 1
    TcpCreate = 2
    TcpConnectExisting = 3


class TextDocumentTestCase(DeferrableTestCase):

    def __init__(self, *args: 'Any', **kwargs: 'Any') -> None:
        super().__init__(*args, **kwargs)
        self.session = None  # type: Optional[Session]
        self.config = make_stdio_test_config()

    def setUp(self) -> 'Generator':
        super().setUp()
        test_name = self.get_test_name()
        server_capabilities = self.get_test_server_capabilities()
        session_type = self.get_test_session_type()
        self.assertTrue(test_name)
        self.assertTrue(server_capabilities)
        if session_type == SessionType.Stdio:
            pass
        elif session_type == SessionType.TcpCreate:
            # TODO: make the test server do TCP
            pass
        elif session_type == SessionType.TcpConnectExisting:
            # TODO
            pass
        else:
            self.assertFalse(True)
        window = sublime.active_window()
        self.assertTrue(window)
        self.config.init_options["serverResponse"] = server_capabilities
        add_config(self.config)
        self.wm = windows.lookup(window)
        self.wm._configs.all.append(self.config)
        filename = expand(join("$packages", "LSP", "tests", "{}.txt".format(test_name)), window)
        open_view = window.find_open_file(filename)
        close_test_view(open_view)
        self.view = window.open_file(filename)
        yield {"condition": lambda: not self.view.is_loading(), "timeout": TIMEOUT_TIME}
        self.assertTrue(self.wm._configs.syntax_supported(self.view))
        self.init_view_settings()
        yield {"condition": self.ensure_document_listener_created, "timeout": TIMEOUT_TIME}
        yield {
            "condition": lambda: self.wm.get_session(self.config.name, self.view.file_name()) is not None,
            "timeout": TIMEOUT_TIME}
        self.session = self.wm.get_session(self.config.name, self.view.file_name())
        self.assertIsNotNone(self.session)
        self.assertEqual(self.session.config.name, self.config.name)
        yield {"condition": lambda: self.session.state == ClientStates.READY, "timeout": TIMEOUT_TIME}
        yield from self.await_boilerplate_begin()

    def get_test_name(self) -> str:
        return "testfile"

    def get_test_server_capabilities(self) -> dict:
        return basic_responses["initialize"]

    def get_test_session_type(self) -> int:
        return SessionType.Stdio

    def init_view_settings(self) -> None:
        s = self.view.settings().set
        s("auto_complete_selector", SUPPORTED_SCOPE)
        s("ensure_newline_at_eof_on_save", False)
        s("rulers", [])
        s("tab_size", 4)
        s("translate_tabs_to_spaces", False)
        s("word_wrap", False)
        s("lsp_format_on_save", False)

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

    def await_message(self, method: str, promise: Optional[YieldPromise] = None) -> 'Generator':
        self.assertIsNotNone(self.session)
        assert self.session  # mypy
        if promise is None:
            promise = YieldPromise()

        def handler(params: Any) -> None:
            promise.fulfill(params)

        def error_handler(params: 'Any') -> None:
            debug("Got error:", params, "awaiting timeout :(")

        self.session.send_request(Request("$test/getReceived", {"method": method}), handler, error_handler)
        yield from self.await_promise(promise)

    def make_server_do_fake_request(self, method: str, params: Any, delay: float = 0) -> YieldPromise:
        promise = YieldPromise()

        def on_result(params: Any) -> None:
            promise.fulfill(params)

        def on_error(params: Any) -> None:
            promise.fulfill(params)

        req = Request("$test/fakeRequest", {"method": method, "params": params, "delay": delay})
        self.session.send_request(req, on_result, on_error)
        return promise

    def make_server_do_fake_notification(self, method: str, params: Any, delay: float = 0) -> None:
        notification = Notification("$test/fakeNotification", {"method": method, "params": params, "delay": delay})
        self.session.send_notification(notification)

    def await_promise(self, promise: YieldPromise) -> Generator:
        yield {"condition": promise, "timeout": TIMEOUT_TIME}

    def set_response(self, method: str, response: 'Any') -> None:
        self.assertIsNotNone(self.session)
        assert self.session  # mypy
        self.session.send_notification(
            Notification("$test/setResponse", {"method": method, "response": response}))

    def await_client_notification(self, method: str, params: 'Any' = None) -> 'Generator':
        self.assertIsNotNone(self.session)
        assert self.session  # mypy
        promise = YieldPromise()

        def handler(params: 'Any') -> None:
            assert params is None
            promise.fulfill()

        def error_handler(params: 'Any') -> None:
            debug("Got error:", params, "awaiting timeout :(")

        self.session.client.send_request(
            Request("$test/sendNotification", {"method": method, "params": params}), handler, error_handler)
        yield {"condition": promise, "timeout": TIMEOUT_TIME}

    def await_boilerplate_begin(self) -> 'Generator':
        yield from self.await_message("initialize")
        yield from self.await_message("initialized")
        yield from self.await_message("textDocument/didOpen")

    def await_boilerplate_end(self) -> 'Generator':
        self.wm.end_config_sessions(self.config.name)  # TODO: Shouldn't this be automatic once the last view closes?
        if self.session:
            yield lambda: self.session.state == ClientStates.STOPPING

    def await_clear_view_and_save(self) -> 'Generator':
        assert self.view  # type: Optional[sublime.View]
        self.view.run_command("select_all")
        self.view.run_command("left_delete")
        self.view.run_command("save")
        yield from self.await_message("textDocument/didChange")
        yield from self.await_message("textDocument/didSave")

    def await_view_change(self, expected_change_count: int) -> 'Generator':
        assert self.view  # type: Optional[sublime.View]

        def condition() -> bool:
            nonlocal self
            nonlocal expected_change_count
            assert self.view
            v = self.view
            return v.change_count() == expected_change_count

        yield {"condition": condition, "timeout": TIMEOUT_TIME}

    def insert_characters(self, characters: str) -> int:
        assert self.view  # type: Optional[sublime.View]
        self.view.run_command("insert", {"characters": characters})
        return self.view.change_count()

    def tearDown(self) -> 'Generator':
        yield from self.await_boilerplate_end()
        super().tearDown()

    def doCleanups(self) -> 'Generator':
        # restore the user's configs
        close_test_view(self.view)
        remove_config(self.config)
        self.wm._configs.all.remove(self.config)
        yield from super().doCleanups()
