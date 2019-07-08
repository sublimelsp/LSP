from setup import TextDocumentTestCase, close_test_view
import sublime
from os.path import dirname

TEST_FILE_PATH = dirname(__file__) + "/goto.txt"

RESPONSE = [
    {
        'uri': TEST_FILE_PATH,
        'range':
        {
            'start':
            {
                'character': 2,
                'line': 0
            },
        }
    }
]


class GotoTestCase(TextDocumentTestCase):

    def setUp(self):
        super().setUp()
        yield 100
        self.view.run_command('insert', {"characters": 'hello there'})
        yield 100
        self.goto_view = sublime.active_window().open_file(TEST_FILE_PATH)
        yield 100
        self.goto_view.run_command('insert', {'characters': 'foo'})
        yield 100
        self.view.window().focus_view(self.view)  # go back to first view
        yield 100

    def tearDown(self):
        close_test_view(self.goto_view)
        super().tearDown()


class LspGotoCommandTests(GotoTestCase):

    def do_common_checks(self):
        yield 100
        view = sublime.active_window().active_view()
        self.checkTrue(view.file_name().endswith("goto.txt"))
        line1, col1 = view.rowcol(view.sel()[0].a)
        line2, col2 = view.rowcol(view.sel()[0].b)
        self.checkEqual(line1, 0)
        self.checkEqual(col1, 2)
        self.checkEqual(line2, 0)
        self.checkEqual(col2, 2)

    def test_definition(self):
        self.client.responses['textDocument/definition'] = RESPONSE
        self.view.run_command('lsp_symbol_definition')
        self.do_common_checks()

    def test_type_definition(self):
        self.client.responses['textDocument/typeDefinition'] = RESPONSE
        self.view.run_command('lsp_symbol_type_definition')
        self.do_common_checks()

    def test_declaration(self):
        self.client.responses['textDocument/declaration'] = RESPONSE
        self.view.run_command('lsp_symbol_declaration')
        self.do_common_checks()

    def test_implementation(self):
        self.client.responses['textDocument/implementation'] = RESPONSE
        self.view.run_command('lsp_symbol_implementation')
        self.do_common_checks()
