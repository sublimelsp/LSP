import sublime
import threading
import json
import time

from sublime_plugin import view_event_listeners
from LSP.plugin.core.types import ClientConfig, LanguageConfig, Settings
from LSP.plugin.core.sessions import Session
from LSP.plugin.core.test_mocks import basic_responses
# from LSP.plugin.core.test_session import MockClient
from LSP.plugin.core.settings import client_configs
from LSP.plugin.core.rpc import Client
from LSP.plugin.core.transports import Transport
from os.path import dirname
from LSP.plugin.core.registry import windows  # , session_for_view
from unittesting import DeferrableTestCase

test_file_path = dirname(__file__) + "/testfile.txt"

SUPPORTED_SCOPE = "text.plain"
SUPPORTED_SYNTAX = "Packages/Text/Plain text.tmLanguage"
text_language = LanguageConfig("text", [SUPPORTED_SCOPE], [SUPPORTED_SYNTAX])
text_config = ClientConfig("textls", [], None, languages=[text_language])

try:
    from typing import Dict, List, Callable, Any
    assert Dict and Callable and List and Any
except ImportError:
    pass


def sublime_delayer(delay):
    def timeout_function(callable):
        sublime.set_timeout(callable, delay)

    return timeout_function


def add_config(config):
    client_configs.all.append(config)


def remove_config(config):
    client_configs.all.remove(config)


def inject_session(wm, config, client) -> Session:
    print("injecting session")
    session = Session(config, "", client, wm._handle_pre_initialize, wm._handle_post_initialize)
    wm._sessions[config.name] = session
    wm.update_configs()
    return session


def remove_session(wm, config_name):
    print("removing session")
    wm._handle_post_exit(config_name)


def close_test_view(view):
    if view:
        view.set_scratch(True)
        view.window().focus_view(view)
        view.window().run_command("close_file")


class TestTransport(Transport):

    def __init__(self, responses: 'Dict[str, dict]') -> None:
        self.sent = []  # type: List[dict]
        self._read_index = -1
        self.responses = responses
        self.stop = False

    def start(self, on_receive: 'Callable[[str], None]', on_closed: 'Callable[[], None]') -> None:
        self._on_receive = on_receive
        self._on_closed = on_closed
        self._reply_thread = threading.Thread(target=self.reply_worker)
        self._reply_thread.start()
        self._log('started reply thread')

    def send(self, message: str) -> None:
        self.sent.append(json.loads(message))
        self._log('received message', len(self.sent))

    def reply_worker(self) -> None:
        while not self.stop:
            self.read_and_reply()
            time.sleep(0.01)
        self._log('reply thread exited')

    def read_and_reply(self) -> None:
        for index in range(self._read_index + 1, len(self.sent)):
            # self._log("reading from total ", len(self.sent), "messages at index", self._read_index)
            self._read_index += 1
            message = self.sent[self._read_index]
            method = message["method"]
            req_id = message.get("id")
            self._log('read', method)
            if req_id and method in self.responses:
                self._log('replying to request', req_id)
                response = {
                    'id': req_id,
                    'result': self.responses[method]
                }
                self._on_receive(json.dumps(response))

        # time.sleep(100)  # yield thread.
    def _log(self, *args: 'Any') -> None:
        print("TestTransport:", *args)


class TextDocumentTestCase(DeferrableTestCase):

    def __init__(self, view):
        super().__init__(view)
        self.test_file_path = test_file_path

    def setUp(self) -> None:
        add_config(text_config)
        self.wm = windows.lookup(sublime.active_window())
        self.wm.update_configs()
        self.transport = TestTransport(basic_responses)
        self.client = Client(self.transport, Settings())
        self.session = inject_session(self.wm, text_config, self.client)
        # from LSP import rpdb; rpdb.set_trace()
        self.view = sublime.active_window().open_file(self.test_file_path)
        self.view.settings().set("auto_complete_selector", "text.plain")
        assert self.wm._configs.syntax_supported(self.view)

    def get_view_event_listener(self, unique_attribute: str):
        for listener in view_event_listeners[self.view.id()]:
            if unique_attribute in dir(listener):
                return listener

    def tearDown(self) -> None:
        self.transport.stop = True
        remove_session(self.wm, text_config.name)
        remove_config(text_config)
        print('closing testfile')
        close_test_view(self.view)
