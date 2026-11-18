from __future__ import annotations

from .setup import TextDocumentTestCase
from .test_single_document import TEST_FILE_PATH
from LSP.plugin import Request
from LSP.plugin.core.protocol import Error
from LSP.plugin.core.protocol import Point
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.diagnostics import DiagnosticsStorage
from LSP.protocol import LSPErrorCodes
from typing import TYPE_CHECKING
from unittest import TestCase

if TYPE_CHECKING:
    from LSP.protocol import Diagnostic
    from LSP.protocol import DiagnosticRegistrationOptions
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


def pull_provider_options(identifier: str) -> DiagnosticRegistrationOptions:
    return {
        'identifier': identifier,
        'interFileDependencies': False,
        'workspaceDiagnostics': False,
        'documentSelector': None,
    }


def range_from_points(start: Point, end: Point) -> Range:
    return {
        'start': start.to_lsp(),
        'end': end.to_lsp()
    }


class DiagnosticsTestCase(TextDocumentTestCase):

    async def test_ignore_result_of_cancelled_request(self) -> None:
        method = 'textDocument/diagnostic'
        await self.mock_response(method, {'kind': 'full', 'items': []})
        request = self.session.request(Request(method, {'textDocument': {'uri': TEST_FILE_URI}}))
        await request.cancel()
        response = await request
        self.assertIsInstance(response, Error)
        self.assertEqual(response.code, LSPErrorCodes.RequestCancelled)
        # The late reply of the server must be swallowed without any side effects.
        await self.await_message(method)

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

    async def test_unregister_pull_provider_removes_its_diagnostics(self) -> None:
        self.insert_characters('const x = 1')
        await self.await_message("textDocument/didChange")
        await self.mock_response('textDocument/diagnostic', {
            'kind': 'full',
            'resultId': 'result-1',
            'items': [{'range': range_from_points(Point(0, 0), Point(0, 5)), 'message': 'pulled'}],
        })
        await self.make_server_do_fake_request('client/registerCapability', {
            'registrations': [
                {'id': 'pull', 'method': 'textDocument/diagnostic', 'registerOptions': pull_provider_options('foo')}
            ]
        })
        session_buffer = self.session.get_session_buffer_for_uri_async(TEST_FILE_URI)
        await self.wait_until(lambda: len(session_buffer.diagnostics) == 1)
        await self.mock_client_notification(
            "textDocument/publishDiagnostics", create_test_diagnostics([('pushed', Point(0, 6), Point(0, 7))])
        )
        self.assertEqual(len(session_buffer.diagnostics), 2)
        self.assertIn((TEST_FILE_URI, 'foo'), self.session.diagnostics_result_ids)

        await self.make_server_do_fake_request('client/unregisterCapability', {
            'unregisterations': [{'id': 'pull', 'method': 'textDocument/diagnostic'}]
        })
        self.assertEqual([d['message'] for d, _ in session_buffer.diagnostics], ['pushed'])
        self.assertNotIn((TEST_FILE_URI, 'foo'), self.session.diagnostics_result_ids)


class DiagnosticsStorageTestCase(TestCase):

    def test_unregister_provider(self) -> None:
        storage = DiagnosticsStorage()
        storage.register_provider('a', pull_provider_options('a'))
        storage.register_provider('b', pull_provider_options('b'))
        storage.register_provider('b2', pull_provider_options('b'))
        storage.set_diagnostics(
            TEST_FILE_URI, 'a', create_test_diagnostics([('a', Point(0, 0), Point(0, 1))])['diagnostics'])
        storage.set_diagnostics(
            TEST_FILE_URI, 'b', create_test_diagnostics([('b', Point(0, 1), Point(0, 2))])['diagnostics'])
        storage.set_diagnostics(
            TEST_FILE_URI, None, create_test_diagnostics([('push', Point(0, 2), Point(0, 3))])['diagnostics'])

        def messages() -> list[str]:
            return [diagnostic['message'] for diagnostic in storage.get_diagnostics_for_uri(TEST_FILE_URI)]

        self.assertEqual(storage.unregister_provider('a'), 'a')
        self.assertEqual(messages(), ['b', 'push'])
        # The identifier "b" is still provided by the provider with registration ID "b2".
        self.assertIsNone(storage.unregister_provider('b'))
        self.assertEqual(messages(), ['b', 'push'])
        self.assertEqual(storage.unregister_provider('b2'), 'b')
        self.assertEqual(messages(), ['push'])
        # Unknown registration IDs are ignored.
        self.assertIsNone(storage.unregister_provider('unknown'))
