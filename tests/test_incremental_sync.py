from LSP.plugin.core.typing import Generator, Tuple
from LSP.plugin.core.url import filename_to_uri
from setup import TextDocumentTestCase
from setup import YieldPromise
from test_single_document import TEST_FILE_PATH


class TestIncrementalSync(TextDocumentTestCase):

    def setUp(self) -> Generator:
        yield from super().setUp()
        self.maxDiff = None

    def verify(self, *args: Tuple[int, int, int, int, int, str]) -> Generator:
        promise = YieldPromise()
        yield from self.await_message("textDocument/didChange", promise)
        content_changes = []
        for arg in args:
            content_changes.append({
                'rangeLength': arg[0],
                'range': {
                    'start': {'line': arg[1], 'character': arg[2]},
                    'end': {'line': arg[3], 'character': arg[4]}},
                'text': arg[5]})
        self.assertEqual(promise.result(), {
            'contentChanges': content_changes,
            'textDocument': {'version': self.view.change_count(), 'uri': filename_to_uri(TEST_FILE_PATH)}
        })

    def test_single_insert(self) -> Generator:
        self.insert_characters("a")
        yield from self.verify(
            (0, 0, 0, 0, 0, 'a')
        )

    def test_neighboring_inserts(self) -> Generator:
        self.insert_characters("a")
        yield 40
        self.insert_characters("b")
        yield 40
        self.insert_characters("c")
        yield from self.verify(
            (0, 0, 0, 0, 0, 'abc')
        )

    def test_did_change(self) -> 'Generator':
        self.insert_characters("A")
        yield from self.await_message("textDocument/didChange")
        # multiple changes are batched into one didChange notification
        self.insert_characters("asdfB\n")
        self.insert_characters("🙂")
        yield from self.verify(
            (0, 0, 1, 0, 1, 'asdfB\n🙂')
        )
        self.insert_characters('x')
        yield from self.verify(
            (0, 1, 2, 1, 2, 'x')  # character offset is 2, because an emoji takes up 2 UTF-16 points.
        )
