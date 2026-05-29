from __future__ import annotations

from .setup import TextDocumentTestCase
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.core.views import entire_content
from pathlib import Path
from typing import Any
from typing import Generator
from typing import TYPE_CHECKING
import os
import tempfile

if TYPE_CHECKING:
    from ..protocol import ApplyWorkspaceEditParams
    from ..protocol import ApplyWorkspaceEditResult
    from ..protocol import WorkspaceEdit


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
        self.assertTrue(self.view.change_count() > old_change_count)
        # `changes` should have been applied
        self.assertEqual(entire_content(self.view), 'hello\nthere\n')

    def test_document_changes(self) -> Generator:
        uri = filename_to_uri(self.view.file_name())
        version = self.insert_characters('hello\nworld\n')
        workspace_edit: WorkspaceEdit = {
            'documentChanges': [
                {
                    'textDocument': {'uri': uri, 'version': version},
                    'edits': [
                        {
                            'range': {'start': {'line': 1, 'character': 0}, 'end': {'line': 1, 'character': 5}},
                            'newText': 'there'
                        }
                    ]
                }
            ]
        }
        params: ApplyWorkspaceEditParams = {'edit': workspace_edit}
        expected_result: ApplyWorkspaceEditResult = {'applied': True}
        yield from verify(self, 'workspace/applyEdit', params, expected_result)
        # `documentChanges` should increase the document version by exactly 1
        self.assertEqual(self.view.change_count(), version + 1)
        # `documentChanges` should have been applied
        self.assertEqual(entire_content(self.view), 'hello\nthere\n')

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
                view = window.open_file(file)
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

    def test_create_file(self) -> Generator:
        window = self.view.window()
        with tempfile.TemporaryDirectory() as dirpath:
            filepath = os.path.join(dirpath, 'newfile.txt')
            uri = filename_to_uri(filepath)
            new_text = 'hello\nworld\n'
            workspace_edit: WorkspaceEdit = {
                'documentChanges': [
                    {
                        'kind': 'create',
                        'uri': uri
                    },
                    {
                        'textDocument': {'uri': uri, 'version': None},
                        'edits': [
                            {
                                'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 0}},
                                'newText': new_text
                            }
                        ]
                    }
                ]
            }
            params: ApplyWorkspaceEditParams = {'edit': workspace_edit}
            expected_result: ApplyWorkspaceEditResult = {'applied': True}
            self.assertFalse(os.path.isfile(filepath))
            yield from verify(self, 'workspace/applyEdit', params, expected_result)
            # The file should have been created
            self.assertTrue(os.path.isfile(filepath))
            # The TextDocumentEdit (second item in `documentChanges`) should have been applied
            content = entire_content(window.open_file(filepath))
            self.assertEqual(content, new_text)

    def test_fails_create_file_exists(self) -> Generator:
        with tempfile.TemporaryDirectory() as dirpath:
            filepath = os.path.join(dirpath, 'newfile.txt')
            old_text = 'hello\nthere\n'
            new_text = 'hello\nworld\n'
            Path(filepath).write_text(old_text, encoding='utf-8')
            uri = filename_to_uri(filepath)
            workspace_edit: WorkspaceEdit = {
                'documentChanges': [
                    {
                        'kind': 'create',
                        'uri': uri
                    },
                    {
                        'textDocument': {'uri': uri, 'version': None},
                        'edits': [
                            {
                                'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 0}},
                                'newText': new_text
                            }
                        ]
                    }
                ]
            }
            params: ApplyWorkspaceEditParams = {'edit': workspace_edit}
            expected_result: ApplyWorkspaceEditResult = {
                'applied': False,
                'failureReason': f'CreateFile failed because a file already exists at target {uri}',
                'failedChange': 0
            }
            yield from verify(self, 'workspace/applyEdit', params, expected_result)
            # The file should still have its original content
            content = Path(filepath).read_text(encoding='utf-8')
            self.assertEqual(content, old_text)

    def test_create_file_exists_ignore(self) -> Generator:
        window = self.view.window()
        with tempfile.TemporaryDirectory() as dirpath:
            filepath = os.path.join(dirpath, 'newfile.txt')
            old_text = 'hello\nthere\n'
            new_text = 'hello\nworld\n'
            Path(filepath).write_text(old_text, encoding='utf-8')
            uri = filename_to_uri(filepath)
            workspace_edit: WorkspaceEdit = {
                'documentChanges': [
                    {
                        'kind': 'create',
                        'uri': uri,
                        'options': {
                            'ignoreIfExists': True
                        }
                    },
                    {
                        'textDocument': {'uri': uri, 'version': None},
                        'edits': [
                            {
                                'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 0}},
                                'newText': new_text
                            }
                        ]
                    }
                ]
            }
            params: ApplyWorkspaceEditParams = {'edit': workspace_edit}
            expected_result: ApplyWorkspaceEditResult = {'applied': True}
            yield from verify(self, 'workspace/applyEdit', params, expected_result)
            # The TextDocumentEdit (second item in `documentChanges`) should have been applied
            content = entire_content(window.open_file(filepath))
            self.assertEqual(content, new_text + old_text)

    def test_create_file_exists_overwrite(self) -> Generator:
        window = self.view.window()
        with tempfile.TemporaryDirectory() as dirpath:
            filepath = os.path.join(dirpath, 'newfile.txt')
            old_text = 'hello\nthere\n'
            new_text = 'hello\nworld\n'
            Path(filepath).write_text(old_text, encoding='utf-8')
            uri = filename_to_uri(filepath)
            workspace_edit: WorkspaceEdit = {
                'documentChanges': [
                    {
                        'kind': 'create',
                        'uri': uri,
                        'options': {
                            'overwrite': True,
                            'ignoreIfExists': True  # Overwrite wins over `ignoreIfExists`
                        }
                    },
                    {
                        'textDocument': {'uri': uri, 'version': None},
                        'edits': [
                            {
                                'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 0}},
                                'newText': new_text
                            }
                        ]
                    }
                ]
            }
            params: ApplyWorkspaceEditParams = {'edit': workspace_edit}
            expected_result: ApplyWorkspaceEditResult = {'applied': True}
            yield from verify(self, 'workspace/applyEdit', params, expected_result)
            # The file content should only be the new text because the file was overwritten
            content = entire_content(window.open_file(filepath))
            self.assertEqual(content, new_text)

    def test_rename_file(self) -> Generator:
        window = self.view.window()
        with tempfile.TemporaryDirectory() as dirpath:
            old_path = os.path.join(dirpath, 'old_file.txt')
            new_path = os.path.join(dirpath, 'new_file.txt')
            old_uri = filename_to_uri(old_path)
            new_uri = filename_to_uri(new_path)
            old_text = 'hello\nthere\n'
            new_text = 'hello\nworld\n'
            Path(old_path).write_text(old_text, encoding='utf-8')
            workspace_edit: WorkspaceEdit = {
                'documentChanges': [
                    {
                        'kind': 'rename',
                        'oldUri': old_uri,
                        'newUri': new_uri
                    },
                    {
                        'textDocument': {'uri': new_uri, 'version': None},
                        'edits': [
                            {
                                'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 0}},
                                'newText': new_text
                            }
                        ]
                    }
                ]
            }
            params: ApplyWorkspaceEditParams = {'edit': workspace_edit}
            expected_result: ApplyWorkspaceEditResult = {'applied': True}
            yield from verify(self, 'workspace/applyEdit', params, expected_result)
            # The file should have been renamed
            self.assertFalse(os.path.isfile(old_path))
            self.assertTrue(os.path.isfile(new_path))
            # The TextDocumentEdit (second item in `documentChanges`) should have been applied
            content = entire_content(window.open_file(new_path))
            self.assertEqual(content, new_text + old_text)

    def test_rename_file_exists(self) -> Generator:
        with tempfile.TemporaryDirectory() as dirpath:
            old_path = os.path.join(dirpath, 'old_file.txt')
            new_path = os.path.join(dirpath, 'new_file.txt')
            old_uri = filename_to_uri(old_path)
            new_uri = filename_to_uri(new_path)
            old_text1 = 'hello\nthere 1\n'
            old_text2 = 'hello\nthere 2\n'
            new_text = 'hello\nworld\n'
            Path(old_path).write_text(old_text1, encoding='utf-8')
            Path(new_path).write_text(old_text2, encoding='utf-8')
            workspace_edit: WorkspaceEdit = {
                'documentChanges': [
                    {
                        'kind': 'rename',
                        'oldUri': old_uri,
                        'newUri': new_uri
                    },
                    {
                        'textDocument': {'uri': new_uri, 'version': None},
                        'edits': [
                            {
                                'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 0}},
                                'newText': new_text
                            }
                        ]
                    }
                ]
            }
            params: ApplyWorkspaceEditParams = {'edit': workspace_edit}
            expected_result: ApplyWorkspaceEditResult = {
                'applied': False,
                'failureReason': f'RenameFile failed because target {new_uri} already exists',
                'failedChange': 0
            }
            yield from verify(self, 'workspace/applyEdit', params, expected_result)
            # The old file should *not* have been deleted (rename operation failed)
            self.assertTrue(os.path.isfile(old_path))
            # The target file should still have its original content
            content = Path(new_path).read_text(encoding='utf-8')
            self.assertEqual(content, old_text2)

    def test_rename_file_exists_ignore(self) -> Generator:
        window = self.view.window()
        with tempfile.TemporaryDirectory() as dirpath:
            old_path = os.path.join(dirpath, 'old_file.txt')
            new_path = os.path.join(dirpath, 'new_file.txt')
            old_uri = filename_to_uri(old_path)
            new_uri = filename_to_uri(new_path)
            old_text1 = 'hello\nthere 1\n'
            old_text2 = 'hello\nthere 2\n'
            new_text = 'hello\nworld\n'
            Path(old_path).write_text(old_text1, encoding='utf-8')
            Path(new_path).write_text(old_text2, encoding='utf-8')
            workspace_edit: WorkspaceEdit = {
                'documentChanges': [
                    {
                        'kind': 'rename',
                        'oldUri': old_uri,
                        'newUri': new_uri,
                        'options': {
                            'ignoreIfExists': True
                        }
                    },
                    {
                        'textDocument': {'uri': new_uri, 'version': None},
                        'edits': [
                            {
                                'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 0}},
                                'newText': new_text
                            }
                        ]
                    }
                ]
            }
            params: ApplyWorkspaceEditParams = {'edit': workspace_edit}
            expected_result: ApplyWorkspaceEditResult = {'applied': True}
            yield from verify(self, 'workspace/applyEdit', params, expected_result)
            # The old file should *not* have been deleted (rename operation ignored)
            self.assertTrue(os.path.isfile(old_path))
            # The TextDocumentEdit (second item in `documentChanges`) should have been applied to the target file
            content = entire_content(window.open_file(new_path))
            self.assertEqual(content, new_text + old_text2)

    def test_rename_file_exists_overwrite(self) -> Generator:
        window = self.view.window()
        with tempfile.TemporaryDirectory() as dirpath:
            old_path = os.path.join(dirpath, 'old_file.txt')
            new_path = os.path.join(dirpath, 'new_file.txt')
            old_uri = filename_to_uri(old_path)
            new_uri = filename_to_uri(new_path)
            old_text1 = 'hello\nthere 1\n'
            old_text2 = 'hello\nthere 2\n'
            new_text = 'hello\nworld\n'
            Path(old_path).write_text(old_text1, encoding='utf-8')
            Path(new_path).write_text(old_text2, encoding='utf-8')
            workspace_edit: WorkspaceEdit = {
                'documentChanges': [
                    {
                        'kind': 'rename',
                        'oldUri': old_uri,
                        'newUri': new_uri,
                        'options': {
                            'overwrite': True,
                            'ignoreIfExists': True  # Overwrite wins over `ignoreIfExists`
                        }
                    },
                    {
                        'textDocument': {'uri': new_uri, 'version': None},
                        'edits': [
                            {
                                'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 0}},
                                'newText': new_text
                            }
                        ]
                    }
                ]
            }
            params: ApplyWorkspaceEditParams = {'edit': workspace_edit}
            expected_result: ApplyWorkspaceEditResult = {'applied': True}
            yield from verify(self, 'workspace/applyEdit', params, expected_result)
            # The old file should have been deleted (rename operation succeeded)
            self.assertFalse(os.path.isfile(old_path))
            # The TextDocumentEdit (second item in `documentChanges`) should have been applied to the renamed file
            content = entire_content(window.open_file(new_path))
            self.assertEqual(content, new_text + old_text1)

    def test_delete_file(self) -> Generator:
        with tempfile.TemporaryDirectory() as dirpath:
            filepath = os.path.join(dirpath, 'newfile.txt')
            Path(filepath).write_text('hello\nworld\n', encoding='utf-8')
            uri = filename_to_uri(filepath)
            workspace_edit: WorkspaceEdit = {
                'documentChanges': [
                    {
                        'kind': 'delete',
                        'uri': uri
                    }
                ]
            }
            params: ApplyWorkspaceEditParams = {'edit': workspace_edit}
            expected_result: ApplyWorkspaceEditResult = {'applied': True}
            self.assertTrue(os.path.isfile(filepath))
            yield from verify(self, 'workspace/applyEdit', params, expected_result)
            # The file should have been deleted
            self.assertFalse(os.path.isfile(filepath))
