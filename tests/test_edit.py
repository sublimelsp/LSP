from unittesting import DeferrableTestCase
from unittest import skip

import sublime

try:
    from typing import Tuple
    assert Tuple
except ImportError:
    pass


class ApplyDocumentEditTests(DeferrableTestCase):
    def setUp(self):
        self.view = sublime.active_window().new_file()

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
            ((1, 2), (1, 2), '5'),  # then insert after the g again
            ((1, 2), (1, 3), '6'),  # replace the just-inserted "5" with a "6"
            ((0, 1), (0, 1), '1'),  # insert "1" after "a"
            ((0, 1), (0, 1), '2'),  # insert "2" after "a"
            ((0, 1), (0, 1), '3'),  # insert "3" after "a"
        ]
        expected = (
            'a321bcde\n'
            'fg64hij\n'
        )
        self.run_test(original, expected, file_changes)

    def test_remove_line_and_then_insert_at_that_line_not_at_end(self):
        original = (
            'a\n'
            'b\n'
            'c'
        )
        file_changes = [
            ((1,0), (2,0), ''),
            ((2,0), (2,0), 'x\n')
        ]
        expected = (
            'a\n'
            'x\n'
            'c'
        )
        self.run_test(original, expected, file_changes)

    @skip("point is out-of-bounds")
    def test_remove_line_and_then_insert_at_that_line_at_end(self):
        original = (
            'a\n'
            'b\n'
            'c'
        )
        file_changes = [
            ((2, 0), (3, 0), ''),  # note out-of-bounds end position
            ((3, 0), (3, 0), 'c\n')  # note out-of-bounds end position
        ]
        expected = (
            'a\n',
            'b\n',
            'c\n'
        )
        # The chain of events is like this:
        # 1) first we end up with ('a\n', 'b\n', 'cc\n')
        # 2) then we end up with ('a\n', 'b\n', '')
        self.run_test(original, expected, file_changes)

    # Quoting the spec:
    # However, it is possible that multiple edits have the same start position: multiple inserts, or any number of
    # inserts followed by a single remove or replace edit. If multiple inserts have the same position, the order in
    # the array defines the order in which the inserted strings appear in the resulting text.

    def test_insertions_at_same_location(self):
        original = ('')
        file_changes = [
            ((0, 0), (0, 0), 'c'),
            ((0, 0), (0, 0), 'b'),
            ((0, 0), (0, 0), 'a')
        ]
        expected = ('abc')
        self.run_test(original, expected, file_changes)

    def test_insertions_followed_by_single_remove(self):
        original = ('def')
        file_changes = [
            ((0, 0), (0, 0), 'c'),
            ((0, 0), (0, 0), 'b'),
            ((0, 0), (0, 0), 'a'),
            ((0, 0), (0, 3), '')
        ]
        expected = ('def')
        self.run_test(original, expected, file_changes)

    def test_insertions_followed_by_single_replace(self):
        original = ('def')
        file_changes = [
            ((0, 0), (0, 0), 'c'),
            ((0, 0), (0, 0), 'b'),
            ((0, 0), (0, 0), 'a'),
            ((0, 0), (0, 4), 'hello')
        ]
        expected = ('helloef')
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
