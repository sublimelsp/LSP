from unittesting import DeferrableTestCase

import sublime

try:
    from typing import Tuple
    assert Tuple
except ImportError:
    pass


class ApplyDocumentEditTests(DeferrableTestCase):
    def setUp(self):
        self.view = sublime.active_window().new_file()

    def test_remove_line_and_then_insert_at_that_line_at_end(self):
        original = (
            'a\n'
            'b\n'
            'c'
        )
        file_changes = [
            ((2, 0), (3, 0), ''),  # out-of-bounds end position, but this is fine
            ((3, 0), (3, 0), 'c\n')  # out-of-bounds start and end, this line doesn't exist
        ]
        expected = (
            'a\n'
            'b\n'
            'c\n'
        )
        # Old behavior:
        # 1) first we end up with ('a\n', 'b\n', 'cc\n')
        # 2) then we end up with ('a\n', 'b\n', '')
        # New behavior:
        # 1) line index 3 is "created" ('a\n', 'b\n', 'c\n', c\n'))
        # 2) deletes line index 2.
        self.run_test(original, expected, file_changes)

    def test_apply(self):
        original = (
            '<dom-module id="some-thing">\n'
            '<style></style>\n'
            '<template>\n'
            '</template>\n'
            '</dom-module>\n'
        )
        file_changes = [
            ((0, 28), (1, 0), ''),  # delete first \n
            ((1, 0), (1, 15), ''),  # delete second line (but not the \n)
            ((2, 10), (2, 10), '\n    <style></style>'),  # insert after <template>
        ]
        expected = (
            '<dom-module id="some-thing">\n'
            '<template>\n'
            '    <style></style>\n'
            '</template>\n'
            '</dom-module>\n'
        )
        self.run_test(original, expected, file_changes)

    def test_apply_and_preserve_order(self):
        original = (
            'abcde\n'
            'fghij\n'
        )
        # Note that (1, 2) comes before (0, 1) in the text.
        file_changes = [
            ((1, 2), (1, 2), '4'),  # insert after the g
            ((1, 2), (1, 2), '5'),
            ((1, 2), (1, 3), '6'),  # replace the h
            ((0, 1), (0, 1), '1'),  # insert after a
            ((0, 1), (0, 1), '2'),
            ((0, 1), (0, 1), '3'),
        ]
        expected = (
            'a123bcde\n'
            'fg456ij\n'
        )
        self.run_test(original, expected, file_changes)

    def run_test(self, original: str, expected: str, file_changes):
        self.view.run_command('insert', {"characters": original})
        self.view.run_command(
            'lsp_apply_document_edit', {'changes': file_changes})
        edited_content = self.view.substr(sublime.Region(0, self.view.size()))
        self.assertEquals(edited_content, expected)

    def tearDown(self):
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")
