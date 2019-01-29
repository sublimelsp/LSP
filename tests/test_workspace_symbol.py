from unittesting import DeferrableTestCase
import sublime
from os.path import dirname
from LSP.plugin.core.types import ClientConfig, ClientStates, LanguageConfig
from LSP.plugin.core.test_session import MockClient
from LSP.plugin.core.sessions import Session
from LSP.plugin.core.registry import windows  # , session_for_view
from LSP.plugin.core.settings import client_configs

target_file = dirname(__file__) + "/testfile.txt"
this_file = __file__


class LspWorkspaceSymbolTests(DeferrableTestCase):

    def setUp(self):
        self.view = sublime.active_window().open_file(this_file)
        self.other_view = None

    def test_workspace_symbol_run(self):
        yield 100  # wait for file to be open
        wm = windows.lookup(self.view.window())
        test_language = LanguageConfig("Python", ["source.python"], ["Packages/Python/Python.sublime-syntax"])
        text_config = ClientConfig("test", [], None, languages=[test_language],)
        client_configs.add_external_config(text_config)
        client_configs.update_configs()
        wm._configs.all.append(text_config)
        client = MockClient()
        session = Session(text_config, dirname(__file__), client)
        session.capabilities = {'workspaceSymbolProvider': True}
        session.state = ClientStates.READY
        wm._sessions[text_config.name] = session

        line = 1
        col = 4
        args = {
            "location": {
                "uri": target_file,
                "range": {
                    "start": {
                        "line": line,
                        "character": col
                    }
                }
            }
        }
        self.view.run_command("lsp_workspace_symbol", {"symbol": args})
        yield 100  # wait for file to be open
        self.other_view = sublime.active_window().active_sheet().view()
        self.assertEquals(self.other_view.file_name(), target_file)
        self.assertEquals(self.other_view.sel()[0].begin(), col - 1)

    def tearDown(self):
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")
        if self.other_view:
            self.other_view.window().focus_view(self.other_view)
            self.other_view.window().run_command("close_file")
