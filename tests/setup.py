from LSP.plugin.core.logging import debug
from LSP.plugin.core.protocol import Notification, Request
from LSP.plugin.core.registry import windows
from LSP.plugin.core.sessions import Session
from LSP.plugin.core.settings import client_configs
from LSP.plugin.core.test_mocks import basic_responses
from LSP.plugin.core.types import ClientConfig, ClientStates, LanguageConfig
from sublime_plugin import view_event_listeners, ViewEventListener
from unittesting import DeferrableTestCase
from LSP.plugin.core.protocol import WorkspaceFolder
from os.path import dirname
import sublime


project_path = dirname(__file__)
test_file_path = project_path + "/testfile.txt"
workspace_folders = [WorkspaceFolder.from_path(project_path)]

SUPPORTED_SCOPE = "text.plain"
SUPPORTED_SYNTAX = "Packages/Text/Plain text.tmLanguage"
text_language = LanguageConfig("text", [SUPPORTED_SCOPE], [SUPPORTED_SYNTAX])
text_config = ClientConfig("textls", [], None, languages=[text_language])

try:
    from typing import Dict, List, Callable, Any, Optional, Generator
    assert Dict and Callable and List and Any and Optional and Generator
except ImportError:
    pass


class YieldPromise:

    __slots__ = ('__done')

    def __init__(self) -> None:
        self.__done = False

    def __call__(self) -> bool:
        return self.__done

    def fulfill(self) -> None:
        assert not self.__done
        self.__done = True


def make_stdio_test_config() -> ClientConfig:
    return ClientConfig(
        name="TEST",
        binary_args=["python3", "$packages/LSP/tests/server.py"],
        tcp_port=None,
        languages=[LanguageConfig(
            language_id="txt",
            scopes=[SUPPORTED_SCOPE],
            syntaxes=[SUPPORTED_SYNTAX])],
        enabled=True)


def sublime_delayer(delay):
    def timeout_function(callable):
        sublime.set_timeout(callable, delay)

    return timeout_function


def add_config(config):
    client_configs.all.append(config)


def remove_config(config):
    client_configs.all.remove(config)


def close_test_view(view: sublime.View):
    if view:
        view.set_scratch(True)
        view.close()


def inject_session(wm, config, client) -> Session:
    session = Session(config, workspace_folders, client, wm._handle_pre_initialize, wm._handle_post_initialize)
    wm._sessions[config.name] = [session]
    wm.update_configs()
    wm._workspace_folders = workspace_folders
    return session


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
        self.old_configs = None   # type: Optional[List[ClientConfig]]
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
            # TODO
            pass
        elif session_type == SessionType.TcpConnectExisting:
            # TODO
            pass
        else:
            self.assertFalse(True)
        window = sublime.active_window()
        self.assertTrue(window)
        filename = expand("$packages/LSP/tests/{}.txt".format(test_name), window)
        # inject what the test server should return for its initialize request here
        self.config.init_options["serverResponse"] = server_capabilities
        windows._windows.clear()  # destroy all window managers
        self.old_configs = client_configs.all.copy()
        client_configs.all.clear()
        add_config(self.config)
        self.wm = windows.lookup(window)  # create just this single one for the test
        self.view = window.open_file(filename)
        self.assertTrue(self.wm._configs.syntax_supported(self.view))
        self.init_view_settings()
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

    def get_view_event_listener(self, unique_attribute: str) -> 'Optional[ViewEventListener]':
        for listener in view_event_listeners[self.view.id()]:
            if unique_attribute in dir(listener):
                return listener
        return None

    def await_session(self) -> 'Generator':

        def condition() -> bool:
            if not self.view:
                return False
            if not self.view.is_valid():
                return False
            if not self.session:
                self.session = self.wm._sessions.get(self.config.name, None)
                if not self.session:
                    print("still no session")
                    return False
            if not self.session.client:
                return False
            if self.session.state != ClientStates.READY:
                return False
            if not self.session.capabilities:
                return False
            return True

        yield {"condition": condition, "timeout": 1000}

    def await_message(self, method: str, expected_session_state: int = ClientStates.READY) -> 'Generator':
        print("AWAIT", method)
        self.assertIsNotNone(self.session)
        assert self.session  # mypy
        self.assertEqual(self.session.state, expected_session_state)
        promise = YieldPromise()

        def handler(params: 'Any') -> None:
            assert params is None
            promise.fulfill()

        def error_handler(params: 'Any') -> None:
            debug("Got error:", params, "awaiting timeout :(")

        self.session.client.send_request(Request("$test/getReceived", {"method": method}), handler, error_handler)
        yield {
            "condition": promise,
            # Enough time for the textDocument/didChange purge delay,
            # but not enough time for the textDocument/willSaveWaitUntil timeout
            "timeout": 900
        }

    def set_response(self, method: str, response: 'Any') -> None:
        self.assertIsNotNone(self.session)
        assert self.session  # mypy
        self.assertEqual(self.session.state, ClientStates.READY)
        self.session.client.send_notification(
            Notification("$test/setResponse", {"method": method, "response": response}))

    def await_boilerplate_begin(self) -> 'Generator':
        yield from self.await_session()
        yield from self.await_message("initialize")
        yield from self.await_message("initialized")
        yield from self.await_message("textDocument/didOpen")

    def await_boilerplate_end(self) -> 'Generator':
        close_test_view(self.view)
        self.wm.end_session(self.config.name)  # TODO: Shouldn't this be automatic once the view closes?
        yield lambda: self.session.state == ClientStates.STOPPING
        yield lambda: self.session.client is None

    def await_clear_view_and_save(self) -> 'Generator':
        assert self.view  # type: Optional[sublime.View]
        self.view.run_command("select_all")
        self.view.run_command("left_delete")
        self.view.run_command("save")
        yield from self.await_message("textDocument/didChange")
        yield from self.await_message("textDocument/didSave")

    def tearDown(self) -> 'Generator':
        yield from self.await_boilerplate_end()
        # restore the user's configs
        client_configs.update_configs()
        super().tearDown()
