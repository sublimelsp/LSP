from LSP.plugin.core.test_mocks import MockClient
from os import remove
from os.path import dirname
from os.path import join
from setup import TextDocumentTestCase
from sublime import Region


class OnPreSaveTests(TextDocumentTestCase):

    def setUp(self):
        self.client = MockClient()
        self.test_file_path = join(dirname(__file__), "on_pre_save.txt")
        super().setUp()

    def tearDown(self):
        remove(self.test_file_path)
        super().tearDown()

    def test_format_on_save(self):
        """
        Open the (empty) file on_pre_save.txt, put the character 'a' in it, and then save it.
        The test language server should remove the 'a' character.
        """
        yield 100
        setup = self.view.settings().set
        setup("ensure_newline_at_eof_on_save", False)
        setup("trim_trailing_white_space_on_save", False)
        setup("lsp_format_on_save", True)
        self.client.responses['textDocument/formatting'] = [{
            "newText": "",
            "range": {
                "start": {"line": 0, "character": 0},
                "end":   {"line": 0, "character": 1}
            }
        }]
        run = self.view.run_command
        run("insert", {"characters": "a"})
        run("save")
        yield 100
        text = self.view.substr(Region(0, self.view.size()))
        self.assertEqual(text, "")
