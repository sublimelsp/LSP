from LSP.plugin.core.edit import sort_by_application_order, parse_workspace_edit, parse_text_edit
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.edit import temporary_setting
from test_protocol import LSP_RANGE
import sublime
import unittest

TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import List, Dict, Optional, Any, Iterable
    assert List and Dict and Optional and Any and Iterable

LSP_TEXT_EDIT = dict(newText='newText', range=LSP_RANGE)
FILENAME = 'C:\\file.py' if sublime.platform() == "windows" else '/file.py'
URI = filename_to_uri(FILENAME)
LSP_EDIT_CHANGES = {'changes': {URI: [LSP_TEXT_EDIT]}}

LSP_EDIT_DOCUMENT_CHANGES = {
    'documentChanges': [{
        'textDocument': {'uri': URI},
        'edits': [LSP_TEXT_EDIT]
    }]
}


class TextEditTests(unittest.TestCase):

    def test_parse_from_lsp(self):
        (start, end, newText, version) = parse_text_edit(LSP_TEXT_EDIT, 0)
        self.assertEqual(newText, 'newText')
        self.assertEqual(start[0], 10)
        self.assertEqual(start[1], 4)
        self.assertEqual(end[0], 11)
        self.assertEqual(end[1], 3)
        self.assertEqual(version, 0)


class WorkspaceEditTests(unittest.TestCase):

    def test_parse_no_changes_from_lsp(self):
        edit = parse_workspace_edit(dict())
        self.assertEqual(len(edit), 0)

    def test_parse_changes_from_lsp(self):
        edit = parse_workspace_edit(LSP_EDIT_CHANGES)
        self.assertIn(FILENAME, edit)
        self.assertEqual(len(edit), 1)
        self.assertEqual(len(edit[FILENAME]), 1)

    def test_parse_document_changes_from_lsp(self):
        edit = parse_workspace_edit(LSP_EDIT_DOCUMENT_CHANGES)
        self.assertIn(FILENAME, edit)
        self.assertEqual(len(edit), 1)
        self.assertEqual(len(edit[FILENAME]), 1)


class SortByApplicationOrderTests(unittest.TestCase):

    def test_empty_sort(self):
        self.assertEqual(sort_by_application_order([]), [])

    def test_sorts_in_application_order(self):
        edits = [
            ((0, 0), (0, 0), 'b'),
            ((0, 0), (0, 0), 'a'),
            ((0, 2), (0, 2), 'c')
        ]
        # expect 'c' (higher start), 'a' now reverse order before 'b'
        sorted_edits = sort_by_application_order(edits)
        self.assertEqual(sorted_edits[0][2], 'b')
        self.assertEqual(sorted_edits[1][2], 'a')
        self.assertEqual(sorted_edits[2][2], 'c')


class TemporarySetting(unittest.TestCase):

    def test_basics(self) -> None:
        v = sublime.active_window().active_view()
        s = v.settings()
        key = "__some_setting_that_should_not_exist__"
        with temporary_setting(s, key, "hello"):
            # The value should be modified while in the with-context
            self.assertEqual(s.get(key), "hello")
        # The key should be erased once out of the with-context, because it was not present before.
        self.assertFalse(s.has(key))
        s.set(key, "hello there")
        with temporary_setting(s, key, "general kenobi"):
            # value key should be modified while in the with-context
            self.assertEqual(s.get(key), "general kenobi")
        # The key should remain present, and the value should be restored.
        self.assertEqual(s.get(key), "hello there")
        s.erase(key)
