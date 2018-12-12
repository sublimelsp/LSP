from unittesting import DeferrableTestCase
import sublime
from os.path import dirname
from LSP.plugin.core.types import ClientConfig, ClientStates, LanguageConfig
from LSP.plugin.core.test_session import MockClient
from LSP.plugin.core.sessions import Session
from LSP.plugin.core.registry import windows  # , session_for_view
from LSP.plugin.core.settings import client_configs

test_file_path = dirname(__file__) + "/testfile.txt"
SUPPORTED_SCOPE = "text.plain"
SUPPORTED_SYNTAX = "Lang.sublime-syntax"
text_config = ClientConfig('langls', [], None, [SUPPORTED_SCOPE], [SUPPORTED_SYNTAX], 'lang')
test_language = LanguageConfig("test", ["text.plain"], ["Plain text"])
# text_config = ClientConfig("test", [], None, languages=[test_language], commands=test_commands,)


class LspExecuteCommandTests(DeferrableTestCase):

    def setUp(self):
        self.view = sublime.active_window().open_file(test_file_path)
        self.old_configs = client_configs.all
        client_configs.all = [text_config]

    def test_execute_command(self):
        wm = windows.lookup(self.view.window())
        wm._configs.all.append(text_config)
        point = self.view.sel()[0].begin()
        print("point " + str(point))
        print("in test {}".format(wm._configs.scope_config(self.view, point)))

        session = Session(text_config, dirname(__file__), MockClient())
        session.initialize()
        session.state = ClientStates.READY
        wm._sessions[text_config.name] = session
        self.view.run_command("lsp_execute_command", {"command_name": "command1"})

    def tearDown(self):
        client_configs.all = self.old_configs
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")
