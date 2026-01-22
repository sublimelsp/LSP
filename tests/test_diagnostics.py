from __future__ import annotations
from LSP.plugin.core.protocol import Point
from LSP.plugin.core.url import filename_to_uri
from setup import TextDocumentTestCase
from test_single_document import TEST_FILE_PATH
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator
    from LSP.protocol import Diagnostic, PublishDiagnosticsParams, Range

TEST_FILE_URI = filename_to_uri(TEST_FILE_PATH)


def create_test_diagnostics(diagnostics: list[tuple[str, Point, Point]]) -> PublishDiagnosticsParams:
    def diagnostic_to_lsp(diagnostic: tuple[str, Point, Point]) -> Diagnostic:
        message, start, end = diagnostic
        return {
            "message": message,
            "range": range_from_points(start, end)
        }
    return {
        "uri": TEST_FILE_URI,
        "diagnostics": list(map(diagnostic_to_lsp, diagnostics))
    }


def range_from_points(start: Point, end: Point) -> Range:
    return {
        'start': start.to_lsp(),
        'end': end.to_lsp()
    }


class DiagnosticsTestCase(TextDocumentTestCase):

    def test_clear_diagnostics_immediately_after_change(self) -> Generator:
        # Trigger specific sequence of events:
        #  1. document has diagnostic issue
        #  2. (async) view is modified
        #  3. (async) publishDiagnostics event comes and clears the diagnostics
        #  4. (async) session gets notified about view changes
        #
        # Verify that the diagnostics are properly cleared.

        def insert_text_and_clear_diagnostics() -> None:
            # Don't wait for result - trigger edit immediately before receiving publishDiagnostics.
            next(self.await_client_notification("textDocument/publishDiagnostics", create_test_diagnostics([])))
            self.insert_characters('// anything')

        self.insert_characters('const x = 1')
        yield from self.await_message("textDocument/didChange")
        yield from self.await_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([('error', Point(0, 0), Point(0, 11))])
        )
        yield from self.run_on_async_thread(insert_text_and_clear_diagnostics)
        session_view = self.session.session_view_for_view_async(self.view)
        self.assertEqual(len(session_view.session_buffer.diagnostics), 0)
