from setup import TextDocumentTestCase
import sublime
from os.path import dirname, join

SELFDIR = dirname(__file__)

TEST_FILE_PATH = join(SELFDIR, 'testfile.txt')

RESPONSE = [
    {
        'uri': TEST_FILE_PATH,
        'range':
        {
            'start':
            {
                # Put the cursor at the capital letter "F".
                'character': 5,
                'line': 1
            },
        }
    }
]

CONTENT = r'''abcdefghijklmnopqrstuvwxyz
ABCDEFGHIJKLMNOPQRSTUVWXYZ
0123456789
'''


def after_cursor(view) -> str:
    first_region = view.sel()[0]
    first = first_region.a
    region = sublime.Region(first, first + 1)
    return view.substr(region)


class GotoTestCase(TextDocumentTestCase):

    def do_run(self, text_document_request: str, subl_command_suffix: str) -> None:
        self.view.run_command('insert', {'characters': CONTENT})
        # Put the cursor back at the start of the buffer, otherwise is_at_word fails in goto.py.
        self.view.sel().clear()
        self.view.sel().add(sublime.Region(0, 0))
        self.client.responses['textDocument/{}'.format(text_document_request)] = RESPONSE
        self.view.run_command('lsp_symbol_{}'.format(subl_command_suffix))

    def do_common_checks(self) -> None:
        filename = self.view.file_name()
        if not filename:
            # self.fail or self.skipTest?
            self.skipTest('view.file_name() returned nothing :(')
            return
        self.assertIn('testfile.txt', filename)
        line1, col1 = self.view.rowcol(self.view.sel()[0].a)
        line2, col2 = self.view.rowcol(self.view.sel()[0].b)
        self.assertEqual(after_cursor(self.view), "F")

    def test_definition(self):
        yield 100
        self.do_run('definition', 'definition')
        yield 100
        self.do_common_checks()

    def test_type_definition(self):
        yield 100
        self.do_run('typeDefinition', 'type_definition')
        yield 100
        self.do_common_checks()

    def test_declaration(self):
        yield 100
        self.do_run('declaration', 'declaration')
        yield 100
        self.do_common_checks()

    def test_implementation(self):
        yield 100
        self.do_run('implementation', 'implementation')
        yield 100
        self.do_common_checks()
