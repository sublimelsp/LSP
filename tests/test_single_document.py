from copy import deepcopy
from LSP.plugin import apply_text_edits, Request
from LSP.plugin.core.protocol import UINT_MAX
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.core.views import entire_content
from LSP.plugin.hover import _test_contents
from setup import TextDocumentTestCase
from setup import TIMEOUT_TIME
from setup import YieldPromise
import os
import sublime


try:
    from typing import Generator, Optional, Iterable, Tuple, List
    assert Generator and Optional and Iterable and Tuple and List
except ImportError:
    pass

SELFDIR = os.path.dirname(__file__)
TEST_FILE_PATH = os.path.join(SELFDIR, 'testfile.txt')
GOTO_RESPONSE = [
    {
        'uri': filename_to_uri(TEST_FILE_PATH),
        'range':
        {
            'start':
            {
                # Put the cursor at the capital letter "F".
                'character': 5,
                'line': 1
            },
            'end':
            {
                'character': 5,
                'line': 1
            }
        }
    }
]
GOTO_RESPONSE_LOCATION_LINK = [
    {
        'originSelectionRange': {'start': {'line': 0, 'character': 0}},
        'targetUri': GOTO_RESPONSE[0]['uri'],
        'targetRange': GOTO_RESPONSE[0]['range'],
        'targetSelectionRange': GOTO_RESPONSE[0]['range']
    }
]
GOTO_CONTENT = r'''abcdefghijklmnopqrstuvwxyz
ABCDEFGHIJKLMNOPQRSTUVWXYZ
0123456789
'''


class SingleDocumentTestCase(TextDocumentTestCase):

    def test_did_open(self) -> None:
        # Just the existence of this method checks "initialize" -> "initialized" -> "textDocument/didOpen"
        # -> "shutdown" -> client shut down
        pass

    def test_did_close(self) -> 'Generator':
        self.assertTrue(self.view)
        self.assertTrue(self.view.is_valid())
        self.view.close()
        yield from self.await_message("textDocument/didClose")

    def test_did_change(self) -> 'Generator':
        assert self.view
        self.maxDiff = None
        self.insert_characters("A")
        yield from self.await_message("textDocument/didChange")
        # multiple changes are batched into one didChange notification
        self.insert_characters("B\n")
        self.insert_characters("🙂\n")
        self.insert_characters("D")
        promise = YieldPromise()
        yield from self.await_message("textDocument/didChange", promise)
        self.assertEqual(promise.result(), {
            'contentChanges': [
                {'rangeLength': 0, 'range': {'start': {'line': 0, 'character': 1}, 'end': {'line': 0, 'character': 1}}, 'text': 'B'},   # noqa
                {'rangeLength': 0, 'range': {'start': {'line': 0, 'character': 2}, 'end': {'line': 0, 'character': 2}}, 'text': '\n'},  # noqa
                {'rangeLength': 0, 'range': {'start': {'line': 1, 'character': 0}, 'end': {'line': 1, 'character': 0}}, 'text': '🙂'},  # noqa
                # Note that this is character offset (2) is correct (UTF-16).
                {'rangeLength': 0, 'range': {'start': {'line': 1, 'character': 2}, 'end': {'line': 1, 'character': 2}}, 'text': '\n'},  # noqa
                {'rangeLength': 0, 'range': {'start': {'line': 2, 'character': 0}, 'end': {'line': 2, 'character': 0}}, 'text': 'D'}],  # noqa
            'textDocument': {
                'version': self.view.change_count(),
                'uri': filename_to_uri(TEST_FILE_PATH)
            }
        })

