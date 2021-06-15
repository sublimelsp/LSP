from LSP.plugin.core.promise import Promise
from LSP.plugin.core.logging import debug
from LSP.plugin.core.protocol import Notification, Request
from LSP.plugin.core.registry import windows
from LSP.plugin.core.settings import client_configs
from LSP.plugin.core.types import ClientConfig, ClientStates
from LSP.plugin.core.typing import Any, Generator, List, Optional, Tuple, Union, Dict
from LSP.plugin.documents import DocumentSyncListener
from os import environ
from os.path import join
from sublime_plugin import view_event_listeners
from test_mocks import basic_responses
from unittesting import DeferrableTestCase
import sublime


CI = any(key in environ for key in ("TRAVIS", "CI", "GITHUB_ACTIONS"))

TIMEOUT_TIME = 10000 if CI else 2000
text_config = ClientConfig(
    name="textls",
    selector="text.plain",
    command=[],
    tcp_port=None)


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
        command=["python3", join("$packages", "LSP", "tests", "server.py")],
        selector="text.plain",
        enabled=True)


def make_tcp_test_config() -> ClientConfig:
    return ClientConfig(
        name="TEST",
        command=["python3", join("$packages", "LSP", "tests", "server.py"), "--tcp-port", "$port"],
        selector="text.plain",
        tcp_port=0,  # select a free one for me
        enabled=True)


def add_config(config):
    client_configs.add_for_testing(config)


def remove_config(config):
    client_configs.remove_for_testing(config)


def close_test_view(view: Optional[sublime.View]) -> 'Generator':
    if view:
        view.set_scratch(True)
        yield {"condition": lambda: not view.is_loading(), "timeout": TIMEOUT_TIME}
        view.close()


def expand(s: str, w: sublime.Window) -> str:
    return sublime.expand_variables(s, w.extract_variables())


class TextDocumentTestCase(DeferrableTestCase):

    @classmethod
    def get_stdio_test_config(cls) -> ClientConfig:
        return make_stdio_test_config()

    @classmethod
    def setUpClass(cls) -> Generator:
        super().setUpClass()
        test_name = cls.get_test_name()
        server_capabilities = cls.get_test_server_capabilities()
        window = sublime.active_window()
        filename = expand(join("$packages", "LSP", "tests", "{}.txt".format(test_name)), window)
        open_view = window.find_open_file(filename)
        yield from close_test_view(open_view)
        cls.config = cls.get_stdio_test_config()
        cls.config.init_options.set("serverResponse", server_capabilities)
        add_config(cls.config)
        cls.wm = windows.lookup(window)
        cls.view = window.open_file(filename)
        yield {"condition": lambda: not cls.view.is_loading(), "timeout": TIMEOUT_TIME}
        yield cls.ensure_document_listener_created
        yield {
            "condition": lambda: cls.wm.get_session(cls.config.name, filename) is not None,
            "timeout": TIMEOUT_TIME}
        cls.session = cls.wm.get_session(cls.config.name, filename)
        yield {"condition": lambda: cls.session.state == ClientStates.READY, "timeout": TIMEOUT_TIME}
        yield from cls.await_message("initialize")
        yield from cls.await_message("initialized")
        yield from close_test_view(cls.view)

    def setUp(self) -> Generator:
        window = sublime.active_window()
        filename = expand(join("$packages", "LSP", "tests", "{}.txt".format(self.get_test_name())), window)
        open_view = window.find_open_file(filename)
        if not open_view:
            self.__class__.view = window.open_file(filename)
            yield {"condition": lambda: not self.view.is_loading(), "timeout": TIMEOUT_TIME}
            self.assertTrue(self.wm._configs.match_view(self.view))
        self.init_view_settings()
        yield self.ensure_document_listener_created
        params = yield from self.await_message("textDocument/didOpen")
        self.assertEquals(params['textDocument']['version'], 0)

    @classmethod
    def get_test_name(cls) -> str:
        return "testfile"

    @classmethod
    def get_test_server_capabilities(cls) -> dict:
        return basic_responses["initialize"]

    @classmethod
    def init_view_settings(cls) -> None:
        s = cls.view.settings().set
        s("auto_complete_selector", "text")
        s("ensure_newline_at_eof_on_save", False)
        s("rulers", [])
        s("tab_size", 4)
        s("translate_tabs_to_spaces", False)
        s("word_wrap", False)
        s("lsp_format_on_save", False)

    @classmethod
    def ensure_document_listener_created(cls) -> bool:
        assert cls.view
        # Bug in ST3? Either that, or CI runs with ST window not in focus and that makes ST3 not trigger some
        # events like on_load_async, on_activated, on_deactivated. That makes things not properly initialize on
        # opening file (manager missing in DocumentSyncListener)
        # Revisit this once we're on ST4.
        for listener in view_event_listeners[cls.view.id()]:
            if isinstance(listener, DocumentSyncListener):
                sublime.set_timeout_async(listener.on_activated_async)
                return True
        return False

    @classmethod
    def await_message(cls, method: str, promise: Optional[YieldPromise] = None) -> 'Generator':
        """
        Awaits until server receives a request with a specified method.

        If the server has already received a request with a specified method before, it will
        immediately return the response for that previous request. If it hasn't received such
        request yet, it will wait for it and then respond.

        :param      method: The method type that we are awaiting response for.
        :param      promise: The optional promise to fullfill on response.

        :returns:   A generator with resolved value.
        """
        # cls.assertIsNotNone(cls.session)
        assert cls.session  # mypy
        if promise is None:
            promise = YieldPromise()

        def handler(params: Any) -> None:
            promise.fulfill(params)

        def error_handler(params: Any) -> None:
            debug("Got error:", params, "awaiting timeout :(")

        cls.session.send_request(Request("$test/getReceived", {"method": method}), handler, error_handler)
        yield from cls.await_promise(promise)
        return promise.result()

    def make_server_do_fake_request(self, method: str, params: Any) -> YieldPromise:
        promise = YieldPromise()

        def on_result(params: Any) -> None:
            promise.fulfill(params)

        def on_error(params: Any) -> None:
            promise.fulfill(params)

        req = Request("$test/fakeRequest", {"method": method, "params": params})
        self.session.send_request(req, on_result, on_error)
        return promise

    @classmethod
    def await_promise(cls, promise: Union[YieldPromise, Promise]) -> Generator:
        if isinstance(promise, YieldPromise):
            yielder = promise
        else:
            yielder = YieldPromise()
            promise.then(lambda result: yielder.fulfill(result))
        yield {"condition": yielder, "timeout": TIMEOUT_TIME}
        return yielder.result()

    def await_run_code_action(self, code_action: Dict[str, Any]) -> Generator:
        promise = YieldPromise()
        sublime.set_timeout_async(
            lambda: self.session.run_code_action_async(code_action, progress=False).then(
                promise.fulfill))
        yield from self.await_promise(promise)

    def set_response(self, method: str, response: Any) -> None:
        self.assertIsNotNone(self.session)
        assert self.session  # mypy
        self.session.send_notification(Notification("$test/setResponse", {"method": method, "response": response}))

    def set_responses(self, responses: List[Tuple[str, Any]]) -> Generator:
        self.assertIsNotNone(self.session)
        assert self.session  # mypy
        promise = YieldPromise()

        def handler(params: Any) -> None:
            promise.fulfill(params)

        def error_handler(params: Any) -> None:
            debug("Got error:", params, "awaiting timeout :(")

        payload = [{"method": method, "response": responses} for method, responses in responses]
        self.session.send_request(Request("$test/setResponses", payload), handler, error_handler)
        yield from self.await_promise(promise)

    def await_client_notification(self, method: str, params: Any = None) -> 'Generator':
        self.assertIsNotNone(self.session)
        assert self.session  # mypy
        promise = YieldPromise()

        def handler(params: Any) -> None:
            promise.fulfill(params)

        def error_handler(params: Any) -> None:
            debug("Got error:", params, "awaiting timeout :(")

        req = Request("$test/sendNotification", {"method": method, "params": params})
        self.session.send_request(req, handler, error_handler)
        yield from self.await_promise(promise)

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

    @classmethod
    def tearDownClass(cls) -> 'Generator':
        if cls.session and cls.wm:
            sublime.set_timeout_async(cls.session.end_async)
            yield lambda: cls.session.state == ClientStates.STOPPING
            if cls.view:
                yield lambda: cls.wm.get_session(cls.config.name, cls.view.file_name()) is None
        cls.session = None
        cls.wm = None
        # restore the user's configs
        remove_config(cls.config)
        super().tearDownClass()

    def doCleanups(self) -> 'Generator':
        if self.view and self.view.is_valid():
            yield from close_test_view(self.view)
        yield from super().doCleanups()
