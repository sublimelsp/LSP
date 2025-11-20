from __future__ import annotations
from LSP.plugin import apply_text_edits
from LSP.plugin.core.edit import parse_workspace_edit
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.core.views import entire_content
from LSP.plugin.edit import _parse_text_edit as parse_text_edit
from LSP.plugin.edit import _sort_by_application_order as sort_by_application_order
from LSP.plugin.edit import temporary_setting
from LSP.protocol import TextDocumentEdit, TextEdit, WorkspaceEdit
from setup import TextDocumentTestCase
from test_protocol import LSP_RANGE
import sublime
import unittest

FILENAME = 'C:\\file.py' if sublime.platform() == "windows" else '/file.py'
URI = filename_to_uri(FILENAME)
LSP_TEXT_EDIT: TextEdit = {
    'newText': 'newText\r\n',
    'range': LSP_RANGE
}

LSP_EDIT_CHANGES: WorkspaceEdit = {
    'changes': {URI: [LSP_TEXT_EDIT]}
}

LSP_TEXT_DOCUMENT_EDIT: TextDocumentEdit = {
    'textDocument': {'uri': URI, 'version': None},
    'edits': [LSP_TEXT_EDIT]
}

LSP_EDIT_DOCUMENT_CHANGES: WorkspaceEdit = {
    'documentChanges': [LSP_TEXT_DOCUMENT_EDIT]
}

# Check that processing document changes does not result in clobbering.
LSP_EDIT_DOCUMENT_CHANGES_2: WorkspaceEdit = {
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

LSP_EDIT_DOCUMENT_CHANGES_3: WorkspaceEdit = {
    'changes': {
        "file:///asdf/foo/bar": [
            {"newText": "hello there", "range": LSP_RANGE},
            {"newText": "general", "range": LSP_RANGE},
            {"newText": "kenobi", "range": LSP_RANGE}
        ]
    },
    'documentChanges': [LSP_TEXT_DOCUMENT_EDIT]
}


class TextEditTests(unittest.TestCase):

    def test_parse_from_lsp(self):
        (start, end, newText) = parse_text_edit(LSP_TEXT_EDIT)
        self.assertEqual(newText, 'newText\n')  # Without the \r
        self.assertEqual(start[0], 10)
        self.assertEqual(start[1], 4)
        self.assertEqual(end[0], 11)
        self.assertEqual(end[1], 3)


class WorkspaceEditTests(unittest.TestCase):

    def test_parse_no_changes_from_lsp(self):
        changes = parse_workspace_edit({})
        self.assertEqual(len(changes), 0)

    def test_parse_changes_from_lsp(self):
        changes = parse_workspace_edit(LSP_EDIT_CHANGES)
        self.assertIn(URI, changes)
        self.assertEqual(len(changes), 1)
        self.assertEqual(len(changes[URI][0]), 1)

    def test_parse_document_changes_from_lsp(self):
        changes = parse_workspace_edit(LSP_EDIT_DOCUMENT_CHANGES)
        self.assertIn(URI, changes)
        self.assertEqual(len(changes), 1)
        self.assertEqual(len(changes[URI][0]), 1)

    def test_no_clobbering_of_previous_edits(self):
        changes = parse_workspace_edit(LSP_EDIT_DOCUMENT_CHANGES_2)
        self.assertIn(URI, changes)
        self.assertEqual(len(changes), 1)
        self.assertEqual(len(changes[URI][0]), 5)

    def test_prefers_document_edits_over_changes(self):
        changes = parse_workspace_edit(LSP_EDIT_DOCUMENT_CHANGES_3)
        self.assertIn(URI, changes)
        self.assertEqual(len(changes), 1)
        self.assertEqual(len(changes[URI][0]), 1)  # not 3


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
        changes = parse_workspace_edit(LSP_EDIT_DOCUMENT_CHANGES_2)
        (edits, version) = changes[URI]
        self.assertEqual(version, 6)
        parsed_edits = [parse_text_edit(edit) for edit in edits]
        sorted_edits = list(reversed(sort_by_application_order(parsed_edits)))
        self.assertEqual(sorted_edits[0][0], (39, 26))
        self.assertEqual(sorted_edits[0][1], (39, 30))
        self.assertEqual(sorted_edits[1][0], (27, 28))
        self.assertEqual(sorted_edits[1][1], (27, 32))


class ApplyDocumentEditTestCase(TextDocumentTestCase):

    def test_applies_text_edit(self) -> None:
        self.insert_characters('abc')
        edits: list[TextEdit] = [{
            'newText': 'x$0y',
            'range': {
                'start': {
                    'line': 0,
                    'character': 1,
                },
                'end': {
                    'line': 0,
                    'character': 2,
                }
            }
        }]
        apply_text_edits(self.view, edits)
        self.assertEqual(entire_content(self.view), 'ax$0yc')

    def test_applies_text_edit_with_placeholder(self) -> None:
        self.insert_characters('abc')
        edits: list[TextEdit] = [{
            'newText': 'x$0y',
            'range': {
                'start': {
                    'line': 0,
                    'character': 1,
                },
                'end': {
                    'line': 0,
                    'character': 2,
                }
            }
        }]
        apply_text_edits(self.view, edits, process_placeholders=True)
        self.assertEqual(entire_content(self.view), 'axyc')
        self.assertEqual(len(self.view.sel()), 1)
        self.assertEqual(self.view.sel()[0], sublime.Region(2, 2))

    def test_applies_multiple_text_edits_with_placeholders(self) -> None:
        self.insert_characters('ab')
        newline_edit: TextEdit = {
            'newText': '\n$0',
            'range': {
                'start': {
                    'line': 0,
                    'character': 1,
                },
                'end': {
                    'line': 0,
                    'character': 1,
                }
            }
        }
        edits: list[TextEdit] = [newline_edit, newline_edit]
        apply_text_edits(self.view, edits, process_placeholders=True)
        self.assertEqual(entire_content(self.view), 'a\n\nb')
        self.assertEqual(len(self.view.sel()), 2)
        self.assertEqual(self.view.sel()[0], sublime.Region(2, 2))
        self.assertEqual(self.view.sel()[1], sublime.Region(3, 3))


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
