import sublime
from sublime_plugin import view_event_listeners
from LSP.plugin.core.types import ClientConfig, LanguageConfig
from LSP.plugin.core.sessions import Session
from LSP.plugin.core.test_session import MockClient
from LSP.plugin.core.settings import client_configs
from os.path import dirname
from LSP.plugin.core.registry import windows  # , session_for_view
from unittesting import DeferrableTestCase

test_file_path = dirname(__file__) + "/testfile.txt"

SUPPORTED_SCOPE = "text.plain"
SUPPORTED_SYNTAX = "Packages/Text/Plain text.tmLanguage"
text_language = LanguageConfig("text", [SUPPORTED_SCOPE], [SUPPORTED_SYNTAX])
text_config = ClientConfig("textls", [], None, languages=[text_language])


def sublime_delayer(delay):
    def timeout_function(callable):
        sublime.set_timeout(callable, delay)

    return timeout_function


def add_config(config):
    client_configs.all.append(config)


def remove_config(config):
    client_configs.all.remove(config)


def inject_session(wm, config, client):

    session = Session(config, "", client)
    # session.state = ClientStates.READY
    wm.update_configs(client_configs.all)
    wm._sessions[config.name] = session
    wm._handle_session_started(session, "", config)


def remove_session(wm, config_name):
    wm._handle_session_ended(config_name)


class TextDocumentTestCase(DeferrableTestCase):

    def setUp(self):
        self.view = sublime.active_window().open_file(test_file_path)
        self.wm = windows.lookup(self.view.window())
        self.client = MockClient(async_response=sublime_delayer(100))
        add_config(text_config)
        inject_session(self.wm, text_config, self.client)
        # from LSP import rpdb; rpdb.set_trace()

    def get_view_event_listener(self, unique_attribute: str):
        for listener in view_event_listeners[self.view.id()]:
            if unique_attribute in dir(listener):
                return listener

    def tearDown(self):
        remove_session(self.wm, text_config.name)
        remove_config(text_config)

        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")
