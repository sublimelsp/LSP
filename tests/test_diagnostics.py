from __future__ import annotations
from LSP.plugin.core.protocol import Point
from LSP.plugin.core.url import filename_to_uri
from setup import TextDocumentTestCase
from test_single_document import TEST_FILE_PATH
from typing import TYPE_CHECKING
from unittesting import AWAIT_WORKER
import sublime

if TYPE_CHECKING:
    from collections.abc import Generator
    from LSP.protocol import Diagnostic, PublishDiagnosticsParams, Range

TEST_FILE_URI = filename_to_uri(TEST_FILE_PATH)


def create_test_diagnostics(
    diagnostics: list[tuple[str, Point, Point]], version: int | None = None
) -> PublishDiagnosticsParams:

    def diagnostic_to_lsp(diagnostic: tuple[str, Point, Point]) -> Diagnostic:
        message, start, end = diagnostic
        return {
            "message": message,
            "range": range_from_points(start, end)
        }

    params: PublishDiagnosticsParams = {
        "uri": TEST_FILE_URI,
        "diagnostics": list(map(diagnostic_to_lsp, diagnostics)),
    }
    if version is not None:
        params["version"] = version
    return params


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

        def insert_text_and_clear_diagnostics_async() -> None:
            self.insert_characters('// anything')
            next(self.await_client_notification("textDocument/publishDiagnostics", create_test_diagnostics([])))

        self.insert_characters('const x = 1')
        yield from self.await_message("textDocument/didChange")
        yield from self.await_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([('error', Point(0, 0), Point(0, 11))])
        )
        session_buffer = self.session.get_session_buffer_for_uri_async(TEST_FILE_URI)
        self.assertEqual(len(session_buffer.diagnostics), 1)

        sublime.set_timeout_async(insert_text_and_clear_diagnostics_async)
        yield AWAIT_WORKER
        # Just a dummy wait to ensure that the `textDocument/publishDiagnostics` triggered from async thread
        # is processed since we can't await it there.
        yield from self.await_client_notification('$/dummy', [])
        self.assertEqual(len(session_buffer.diagnostics), 0)

    def test_ignores_publish_diagnostics_version(self) -> Generator:
        self.insert_characters('const x = 1')
        yield from self.await_message("textDocument/didChange")
        yield from self.await_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([('error', Point(0, 0), Point(0, 11))])
        )
        session_buffer = self.session.get_session_buffer_for_uri_async(TEST_FILE_URI)
        self.assertEqual(len(session_buffer.diagnostics), 1)
        yield from self.await_client_notification(
            "textDocument/publishDiagnostics", create_test_diagnostics([], version=1000)
        )
        self.assertEqual(len(session_buffer.diagnostics), 0)
