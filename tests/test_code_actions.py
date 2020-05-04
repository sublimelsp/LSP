from LSP.plugin.core.protocol import Point, Range
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.core.views import entire_content
from LSP.plugin.code_actions import run_code_action_or_command
from setup import TextDocumentTestCase
from test_single_document import TEST_FILE_PATH

try:
    from typing import Generator, Optional, Iterable, Tuple, List, Dict
    assert Generator and Optional and Iterable and Tuple and List and Dict
except ImportError:
    pass

TEST_FILE_URI = filename_to_uri(TEST_FILE_PATH)


def create_test_code_actions(title: str, document_version: int, edits: 'List[Tuple[str, Range]]') -> 'Dict':
    def edit_to_lsp(edit: 'Tuple[str, Range]') -> 'Dict':
        new_text, range = edit
        return {
            "newText": new_text,
            "range": range.to_lsp()
        }
    return {
        "title": title,
        "edit": {
            "documentChanges": [
                {
                    "textDocument": {
                        "uri": TEST_FILE_URI,
                        "version": document_version
                    },
                    "edits": list(map(edit_to_lsp, edits))
                }
            ]
        }
    }


class CodeActionsTestCase(TextDocumentTestCase):
    def test_applies_code_actions(self) -> 'Generator':
        self.insert_characters('a\nb')
        yield from self.await_message("textDocument/didChange")
        code_actions = create_test_code_actions("Fix errors", self.view.change_count(), [
            ("c", Range(Point(0, 0), Point(0, 1))),
            ("d", Range(Point(1, 0), Point(1, 1))),
        ])
        run_code_action_or_command(self.view, self.config.name, code_actions)
        self.assertEquals(entire_content(self.view), 'c\nd')

    def test_does_not_apply_with_nonmatching_document_version(self) -> 'Generator':
        initial_content = 'a\nb'
        self.insert_characters(initial_content)
        yield from self.await_message("textDocument/didChange")
        code_actions = create_test_code_actions("Fix errors", 0, [
            ("c", Range(Point(0, 0), Point(0, 1))),
            ("d", Range(Point(1, 0), Point(1, 1))),
        ])
        run_code_action_or_command(self.view, self.config.name, code_actions)
        self.assertEquals(entire_content(self.view), initial_content)
