from __future__ import annotations

from ..protocol import ApplyWorkspaceEditParams
from ..protocol import ApplyWorkspaceEditResult
from ..protocol import WorkspaceEdit
from .setup import TextDocumentTestCase
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.core.views import entire_content
from pathlib import Path
from typing import Any
from typing import Generator
import os
import tempfile


def verify(testcase: TextDocumentTestCase, method: str, input_params: Any, expected_result: Any) -> Generator:
    promise = testcase.make_server_do_fake_request(method, input_params)
    yield from testcase.await_promise(promise)
    testcase.assertEqual(promise.result(), expected_result)


class ApplyWorkspaceEditTests(TextDocumentTestCase):

    def test_changes(self) -> Generator:
        old_change_count = self.insert_characters('hello\nworld\n')
        uri = filename_to_uri(self.view.file_name())
        workspace_edit: WorkspaceEdit = {
            'changes': {
                uri: [
                    {
                        'range': {'start': {'line': 1, 'character': 0}, 'end': {'line': 1, 'character': 5}},
                        'newText': 'there'
                    }
                ]
            }
        }
        params: ApplyWorkspaceEditParams = {'edit': workspace_edit}
        expected_result: ApplyWorkspaceEditResult = {'applied': True}
        yield from verify(self, 'workspace/applyEdit', params, expected_result)
        # `changes` should increase the document version
        yield lambda: self.view.change_count() > old_change_count
        # `changes` should have been applied
        self.assertEqual(entire_content(self.view), 'hello\nthere\n')

    def test_document_changes(self) -> Generator:
        uri = filename_to_uri(self.view.file_name())
        version = self.view.change_count()
        workspace_edit: WorkspaceEdit = {
            'documentChanges': [
                {
                    'textDocument': {'uri': uri, 'version': version},
                    'edits': [
                        {
                            'range': {'start': {'line': 1, 'character': 0}, 'end': {'line': 1, 'character': 5}},
                            'newText': 'world'
                        }
                    ]
                }
            ]
        }
        params: ApplyWorkspaceEditParams = {'edit': workspace_edit}
        expected_result: ApplyWorkspaceEditResult = {'applied': True}
        yield from verify(self, 'workspace/applyEdit', params, expected_result)
        # `documentChanges` should increase the document version by exactly 1
        yield lambda: self.view.change_count() == version + 1
        # `documentChanges` should have been applied
        self.assertEqual(entire_content(self.view), 'hello\nworld\n')

    def test_changes_for_unopened_files(self) -> Generator:
        with tempfile.TemporaryDirectory() as dirpath:
            file1 = os.path.join(dirpath, 'file1.txt')
            file2 = os.path.join(dirpath, 'file2.txt')
            Path(file1).write_text('a b', encoding='utf-8')
            Path(file2).write_text('c d', encoding='utf-8')
            uri1 = filename_to_uri(file1)
            uri2 = filename_to_uri(file2)
            workspace_edit: WorkspaceEdit = {
                'changes': {
                    uri1: [
                        {
                            'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 1}},
                            'newText': 'hello'
                        },
                        {
                            'range': {'start': {'line': 0, 'character': 2}, 'end': {'line': 0, 'character': 3}},
                            'newText': 'there'
                        }
                    ],
                    uri2: [
                        {
                            'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 1}},
                            'newText': 'general'
                        },
                        {
                            'range': {'start': {'line': 0, 'character': 2}, 'end': {'line': 0, 'character': 3}},
                            'newText': 'kenobi'
                        }
                    ]
                }
            }
            params: ApplyWorkspaceEditParams = {'edit': workspace_edit}
            expected_result: ApplyWorkspaceEditResult = {'applied': True}
            yield from verify(self, 'workspace/applyEdit', params, expected_result)
            # Changes should have been applied
            window = self.view.window()
            for file, expected_text in zip([file1, file2], ['hello there', 'general kenobi']):
                view = window.find_open_file(file)
                self.assertTrue(view)
                self.assertEqual(entire_content(view), expected_text)
                view.set_scratch(True)
                view.close()

    def test_fails_on_wrong_uri(self) -> Generator:
        uri = 'file:///C:/wrong/uri.txt'
        workspace_edit: WorkspaceEdit = {
            'documentChanges': [
                {
                    'textDocument': {'uri': uri, 'version': None},
                    'edits': [
                        {
                            'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 1}},
                            'newText': 'hello'
                        }
                    ]
                }
            ]
        }
        params: ApplyWorkspaceEditParams = {'edit': workspace_edit}
        expected_result: ApplyWorkspaceEditResult = {
            'applied': False,
            'failureReason': f'Failed to open URI {uri}',
            'failedChange': 0
        }
        yield from verify(self, 'workspace/applyEdit', params, expected_result)

    def test_fails_on_wrong_document_version(self) -> Generator:
        change_count = self.view.change_count()
        uri = filename_to_uri(self.view.file_name())
        version = change_count - 1
        workspace_edit: WorkspaceEdit = {
            'documentChanges': [
                {
                    'textDocument': {'uri': uri, 'version': version},
                    'edits': [
                        {
                            'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 1}},
                            'newText': 'hello'
                        }
                    ]
                }
            ]
        }
        params: ApplyWorkspaceEditParams = {'edit': workspace_edit}
        expected_result: ApplyWorkspaceEditResult = {
            'applied': False,
            'failureReason': f'Document version for URI {uri} is {change_count}, but required {version}',
            'failedChange': 0
        }
        yield from verify(self, 'workspace/applyEdit', params, expected_result)
