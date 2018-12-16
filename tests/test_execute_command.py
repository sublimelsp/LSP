from unittesting import DeferrableTestCase
import sublime
from os.path import dirname
from LSP.plugin.core.types import ClientConfig, ClientStates, LanguageConfig
from LSP.plugin.core.test_session import MockClient
from LSP.plugin.core.sessions import Session
from LSP.plugin.core.registry import windows  # , session_for_view
from LSP.plugin.core.settings import client_configs

test_file_path = __file__


class LspExecuteCommandTests(DeferrableTestCase):

    def setUp(self):
        self.view = sublime.active_window().open_file(test_file_path)

    def test_execute_command_success(self):
        yield 100  # wait for file to be open
        self.view.window().focus_view(self.view)
        wm = windows.lookup(self.view.window())
        test_language = LanguageConfig("Python", ["source.python"], ["Packages/Python/Python.sublime-syntax"])
        text_config = ClientConfig("test", [], None, languages=[test_language],)
        client_configs.add_external_config(text_config)
        client_configs.update_configs()
        wm._configs.all.append(text_config)

        client = MockClient()
        session = Session(text_config, dirname(__file__), client)
        session.state = ClientStates.READY
        wm._sessions[text_config.name] = session

        self.view.run_command("lsp_execute", {"command_name": "command1"})
        self.assertEquals(client._responses[1], {})

    def test_execute_command_failure(self):
        yield 100  # wait for file to be open
        self.view.window().focus_view(self.view)
        wm = windows.lookup(self.view.window())
        test_language = LanguageConfig("Python", ["source.python"], ["Packages/Python/Python.sublime-syntax"])
        text_config = ClientConfig("test", [], None, languages=[test_language],)
        client_configs.add_external_config(text_config)
        client_configs.update_configs()
        wm._configs.all.append(text_config)

        client = MockClient({'workspace/executeCommand': "unknown command"})
        session = Session(text_config, dirname(__file__), client)
        session.state = ClientStates.READY
        wm._sessions[text_config.name] = session

        self.view.run_command("lsp_execute", {"command_name": "command1"})
        self.assertTrue(self.view.is_popup_visible())
        self.assertEquals(client._responses[1], "unknown command")

    def tearDown(self):
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")
