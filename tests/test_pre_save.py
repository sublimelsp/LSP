from os import remove
from os.path import dirname
from os.path import join
from setup import TextDocumentTestCase
from sublime import Region


class OnPreSaveTests(TextDocumentTestCase):

    def setUp(self):
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
        settings = self.view.settings()
        settings.set("ensure_newline_at_eof_on_save", False)
        settings.set("trim_trailing_white_space_on_save", False)
        settings.set("lsp_format_on_save", True)
        self.client.responses['textDocument/formatting'] = [{
            "newText": "",
            "range": {
                "start": {"line": 0, "character": 0},
                "end":   {"line": 0, "character": 1}
            }
        }]
        self.view.run_command("insert", {"characters": "a"})
        self.view.run_command("save")
        yield 100
        text = self.view.substr(Region(0, self.view.size()))
        self.assertEqual(text, "")
