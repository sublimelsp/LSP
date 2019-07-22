from setup import TextDocumentTestCase, close_test_view
import sublime
from os.path import dirname, join

SELFDIR = dirname(__file__)
TEST_FILE_PATH = join(SELFDIR, 'goto.txt')

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
        self.view.run_command('insert', {'characters': 'hello there'})
        self.goto_view = sublime.active_window().open_file(TEST_FILE_PATH)
        yield 100
        self.goto_view.run_command('insert', {'characters': 'foo'})
        self.view.window().focus_view(self.view)  # go back to first view

    def tearDown(self):
        close_test_view(self.goto_view)
        super().tearDown()

    def do_common_checks(self):
        view = sublime.active_window().active_view()
        if not view:
            # self.fail or self.skipTest?
            # self.fail could become annoying when a pull-request sporadically
            # fails for this reason. I (rwols) think we should use skipTest.
            self.skipTest('invalid Sublime Text view :(')
            return
        filename = view.file_name()
        if not filename:
            # self.fail or self.skipTest?
            self.skipTest('view.file_name() returned nothing :(')
            return
        self.assertIn('goto.txt', filename)
        line1, col1 = view.rowcol(view.sel()[0].a)
        line2, col2 = view.rowcol(view.sel()[0].b)
        self.assertEqual(line1, 0)
        self.assertEqual(col1, 2)
        self.assertEqual(line2, 0)
        self.assertEqual(col2, 2)

    def do_run(self, text_document_request: str, subl_command_suffix: str) -> None:
        self.client.responses['textDocument/' + text_document_request] = RESPONSE
        self.view.run_command('lsp_symbol_' + subl_command_suffix)

    def test_definition(self):
        self.do_run('definition', 'definition')
        yield 100
        self.do_common_checks()

    def test_type_definition(self):
        self.do_run('typeDefinition', 'type_definition')
        yield 100
        self.do_common_checks()

    def test_declaration(self):
        self.do_run('declaration', 'declaration')
        yield 100
        self.do_common_checks()

    def test_implementation(self):
        self.do_run('implementation', 'implementation')
        yield 100
        self.do_common_checks()
