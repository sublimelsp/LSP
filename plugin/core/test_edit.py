import unittest
from .edit import sort_by_application_order, parse_workspace_edit, parse_text_edit
from .test_protocol import LSP_RANGE

try:
    from typing import List, Dict, Optional, Any, Iterable, Tuple
    from .edit import TextEdit
    assert List and Dict and Optional and Any and Iterable and Tuple and TextEdit
except ImportError:
    pass

LSP_TEXT_EDIT = dict(newText='newText', range=LSP_RANGE)

LSP_EDIT_CHANGES = {
    'changes': {
        'file:///file.py': [LSP_TEXT_EDIT]
    }
}

LSP_EDIT_DOCUMENT_CHANGES = {
    'documentChanges': [{
        'textDocument': {'uri': 'file:///file.py'},
        'edits': [LSP_TEXT_EDIT]
    }]
}


class TextEditTests(unittest.TestCase):

    def test_parse_from_lsp(self):
        (start, end, newText) = parse_text_edit(LSP_TEXT_EDIT)
        self.assertEqual(newText, 'newText')
        self.assertEqual(start[0], 10)
        self.assertEqual(start[1], 4)
        self.assertEqual(end[0], 11)
        self.assertEqual(end[1], 3)


class WorkspaceEditTests(unittest.TestCase):

    def test_parse_no_changes_from_lsp(self):
        edit = parse_workspace_edit(dict())
        self.assertEqual(len(edit), 0)

    def test_parse_changes_from_lsp(self):
        edit = parse_workspace_edit(LSP_EDIT_CHANGES)
        self.assertEqual(len(edit), 1)
        self.assertEqual(len(edit['/file.py']), 1)

    def test_parse_document_changes_from_lsp(self):
        edit = parse_workspace_edit(LSP_EDIT_DOCUMENT_CHANGES)
        self.assertEqual(len(edit), 1)
        self.assertEqual(len(edit['/file.py']), 1)


class SortByApplicationOrderTests(unittest.TestCase):

    def test_empty_sort(self):
        self.assertEqual(sort_by_application_order([]), [])

    def test_sorts_backwards(self):
        edits = [
            ((0, 0), (0, 0), 'b'),
            ((0, 0), (0, 0), 'a'),
            ((0, 2), (0, 2), 'c')
        ]
        # expect 'c' (higher start), 'a' now reverse order before 'b'
        sorted = sort_by_application_order(edits)
        self.assertEqual(sorted[0][2], 'c')
        self.assertEqual(sorted[1][2], 'a')
        self.assertEqual(sorted[2][2], 'b')
