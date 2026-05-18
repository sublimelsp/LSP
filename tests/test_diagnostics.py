from __future__ import annotations

from .setup import TextDocumentTestCase
from .test_single_document import TEST_FILE_PATH
from LSP.plugin.core.protocol import Point
from LSP.plugin.core.url import filename_to_uri
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from LSP.protocol import Diagnostic
    from LSP.protocol import PublishDiagnosticsParams
    from LSP.protocol import Range

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

    async def test_clear_diagnostics_immediately_after_change(self) -> None:
        # Trigger specific sequence of events:
        #  1. document has diagnostic issue
        #  2. (async) view is modified
        #  3. (async) publishDiagnostics event comes and clears the diagnostics
        #  4. (async) session gets notified about view changes
        #
        # Verify that the diagnostics are properly cleared.
        self.insert_characters('const x = 1')
        await self.await_message("textDocument/didChange")
        await self.mock_client_notification(
            "textDocument/publishDiagnostics",
            create_test_diagnostics([('error', Point(0, 0), Point(0, 11))])
        )
        session_buffer = self.session.get_session_buffer_for_uri_async(TEST_FILE_URI)
        self.assertEqual(len(session_buffer.diagnostics), 1)

        # Insert characters and clear diagnostics.
        self.insert_characters('// anything')
        await self.mock_client_notification("textDocument/publishDiagnostics", create_test_diagnostics([]))

        # Just a dummy wait to ensure that the `textDocument/publishDiagnostics` triggered from async thread
        # is processed since we can't await it there.
        await self.mock_client_notification('$/dummy', [])
        self.assertEqual(len(session_buffer.diagnostics), 0)

    async def test_ignores_publish_diagnostics_version(self) -> None:
        self.insert_characters('const x = 1')
        await self.await_message("textDocument/didChange")
        await self.mock_client_notification(
            "textDocument/publishDiagnostics", create_test_diagnostics([('error', Point(0, 0), Point(0, 11))])
        )
        session_buffer = self.session.get_session_buffer_for_uri_async(TEST_FILE_URI)
        self.assertEqual(len(session_buffer.diagnostics), 1)
        await self.mock_client_notification(
            "textDocument/publishDiagnostics", create_test_diagnostics([], version=1000)
        )
        self.assertEqual(len(session_buffer.diagnostics), 0)

    async def test_handles_unknown_tag_gracefully(self) -> None:
        self.insert_characters('const x = 1')
        await self.await_message("textDocument/didChange")
        await self.mock_client_notification(
            "textDocument/publishDiagnostics",
            {
                "uri": TEST_FILE_URI,
                "diagnostics": [
                    {
                        "range": range_from_points(Point(0, 0), Point(0, 11)),
                        "message": "error",
                        "tags": [42]
                    }
                ]
            }
        )
        session_buffer = self.session.get_session_buffer_for_uri_async(TEST_FILE_URI)
        self.assertEqual(len(session_buffer.diagnostics), 1)

    async def test_handles_multiple_tags(self) -> None:
        self.insert_characters('const x = 1')
        await self.await_message("textDocument/didChange")
        await self.mock_client_notification(
            "textDocument/publishDiagnostics",
            {
                "uri": TEST_FILE_URI,
                "diagnostics": [
                    {
                        "range": range_from_points(Point(0, 0), Point(0, 11)),
                        "message": "unnecessary and deprecated code",
                        "tags": [1, 2]
                    }
                ]
            }
        )
        session_buffer = self.session.get_session_buffer_for_uri_async(TEST_FILE_URI)
        self.assertEqual(len(session_buffer.diagnostics), 1)
