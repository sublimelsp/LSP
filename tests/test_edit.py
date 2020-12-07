from LSP.plugin.core.edit import sort_by_application_order, parse_workspace_edit, parse_text_edit
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.edit import temporary_setting
from test_protocol import LSP_RANGE
from test_mocks import TEST_CONFIG
import sublime
import unittest

TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import List, Dict, Optional, Any, Iterable
    assert List and Dict and Optional and Any and Iterable

LSP_TEXT_EDIT = dict(newText='newText\r\n', range=LSP_RANGE)
FILENAME = 'C:\\file.py' if sublime.platform() == "windows" else '/file.py'
URI = filename_to_uri(FILENAME)
LSP_EDIT_CHANGES = {'changes': {URI: [LSP_TEXT_EDIT]}}

LSP_EDIT_DOCUMENT_CHANGES = {
    'documentChanges': [{
        'textDocument': {'uri': URI},
        'edits': [LSP_TEXT_EDIT]
    }]
}

LSP_EDIT_DOCUMENT_CHANGES_2 = {
    'changes': None,
    'documentChanges': [{
        'textDocument': {'uri': URI},
        'edits': [LSP_TEXT_EDIT]
    }]
}

# Check that processing document changes does not result in clobbering.
LSP_EDIT_DOCUMENT_CHANGES_3 = {
    "documentChanges": [
        {
            "edits": [
                {
                    "range": {
                        "end": {
                            "character": 9,
                            "line": 14
                        },
                        "start": {
                            "character": 5,
                            "line": 14
                        }
                    },
                    "newText": "Test"
                }
            ],
            "textDocument": {
                "uri": URI,
                "version": 6
            }
        },
        {
            "edits": [
                {
                    "range": {
                        "end": {
                            "character": 25,
                            "line": 11
                        },
                        "start": {
                            "character": 21,
                            "line": 11
                        }
                    },
                    "newText": "Test"
                }
            ],
            "textDocument": {
                "uri": URI,
                "version": 6
            }
        },
        {
            "edits": [
                {
                    "range": {
                        "end": {
                            "character": 32,
                            "line": 26
                        },
                        "start": {
                            "character": 28,
                            "line": 26
                        }
                    },
                    "newText": "Test"
                }
            ],
            "textDocument": {
                "uri": URI,
                "version": 6
            }
        },
        {
            "edits": [
                {
                    "range": {
                        "end": {
                            "character": 32,
                            "line": 27
                        },
                        "start": {
                            "character": 28,
                            "line": 27
                        }
                    },
                    "newText": "Test"
                }
            ],
            "textDocument": {
                "uri": URI,
                "version": 6
            }
        },
        {
            "edits": [
                {
                    "range": {
                        "end": {
                            "character": 30,
                            "line": 39
                        },
                        "start": {
                            "character": 26,
                            "line": 39
                        }
                    },
                    "newText": "Test"
                }
            ],
            "textDocument": {
                "uri": URI,
                "version": 6
            }
        }
    ]
}


class TextEditTests(unittest.TestCase):

    def test_parse_from_lsp(self):
        (start, end, newText, version) = parse_text_edit(LSP_TEXT_EDIT, 0)
        self.assertEqual(newText, 'newText\n')  # Without the \r
        self.assertEqual(start[0], 10)
        self.assertEqual(start[1], 4)
        self.assertEqual(end[0], 11)
        self.assertEqual(end[1], 3)
        self.assertEqual(version, 0)


class WorkspaceEditTests(unittest.TestCase):

    def test_parse_no_changes_from_lsp(self):
        edit = parse_workspace_edit(TEST_CONFIG, dict())
        self.assertEqual(len(edit), 0)

    def test_parse_changes_from_lsp(self):
        edit = parse_workspace_edit(TEST_CONFIG, LSP_EDIT_CHANGES)
        self.assertIn(FILENAME, edit)
        self.assertEqual(len(edit), 1)
        self.assertEqual(len(edit[FILENAME]), 1)

    def test_parse_document_changes_from_lsp(self):
        edit = parse_workspace_edit(TEST_CONFIG, LSP_EDIT_DOCUMENT_CHANGES)
        self.assertIn(FILENAME, edit)
        self.assertEqual(len(edit), 1)
        self.assertEqual(len(edit[FILENAME]), 1)

    def test_protocol_violation(self):
        # This should ignore the None in 'changes'
        edit = parse_workspace_edit(TEST_CONFIG, LSP_EDIT_DOCUMENT_CHANGES_2)
        self.assertIn(FILENAME, edit)
        self.assertEqual(len(edit), 1)
        self.assertEqual(len(edit[FILENAME]), 1)

    def test_no_clobbering_of_previous_edits(self):
        edit = parse_workspace_edit(TEST_CONFIG, LSP_EDIT_DOCUMENT_CHANGES_3)
        self.assertIn(FILENAME, edit)
        self.assertEqual(len(edit), 1)
        self.assertEqual(len(edit[FILENAME]), 5)


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

    def test_sorts_in_application_order2(self):
        edits = parse_workspace_edit(TEST_CONFIG, LSP_EDIT_DOCUMENT_CHANGES_3)
        sorted_edits = list(reversed(sort_by_application_order(edits[FILENAME])))
        self.assertEqual(sorted_edits[0][0], (39, 26))
        self.assertEqual(sorted_edits[0][1], (39, 30))
        self.assertEqual(sorted_edits[1][0], (27, 28))
        self.assertEqual(sorted_edits[1][1], (27, 32))


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
