from __future__ import annotations

from .setup import TextDocumentTestCase
from LSP.plugin.core.url import filename_to_uri
from pathlib import Path
from typing import Any
from typing import Generator
import os
import sublime
import tempfile


def verify(testcase: TextDocumentTestCase, method: str, input_params: Any, expected_result: Any) -> Generator:
    promise = testcase.make_server_do_fake_request(method, input_params)
    yield from testcase.await_promise(promise)
    testcase.assertEqual(promise.result(), expected_result)


class ApplyWorkspaceEditTests(TextDocumentTestCase):

    def test_m_workspace_applyEdit(self) -> Generator:
        old_change_count = self.insert_characters("hello\nworld\n")
        edit = {
            "newText": "there",
            "range": {"start": {"line": 1, "character": 0}, "end": {"line": 1, "character": 5}}}
        params = {"edit": {"changes": {filename_to_uri(self.view.file_name()): [edit]}}}
        yield from verify(self, "workspace/applyEdit", params, {"applied": True})
        yield lambda: self.view.change_count() > old_change_count
        self.assertEqual(self.view.substr(sublime.Region(0, self.view.size())), "hello\nthere\n")

    def test_m_workspace_applyEdit_with_nontrivial_promises(self) -> Generator:
        with tempfile.TemporaryDirectory() as dirpath:
            initial_text = ["a b", "c d"]
            file_paths = []
            for i in range(2):
                file_paths.append(os.path.join(dirpath, f"file{i}.txt"))
                Path(file_paths[-1]).write_text(initial_text[i], encoding="utf-8")
            yield from verify(
                self,
                "workspace/applyEdit",
                {
                    "edit": {
                        "changes": {
                            filename_to_uri(file_paths[0]):
                            [
                                {
                                    "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 1}},
                                    "newText": "hello"
                                },
                                {
                                    "range": {"start": {"line": 0, "character": 2}, "end": {"line": 0, "character": 3}},
                                    "newText": "there"
                                }
                            ],
                            filename_to_uri(file_paths[1]):
                            [
                                {
                                    "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 1}},
                                    "newText": "general"
                                },
                                {
                                    "range": {"start": {"line": 0, "character": 2}, "end": {"line": 0, "character": 3}},
                                    "newText": "kenobi"
                                }
                            ]
                        }
                    }
                },
                {"applied": True}
            )
            # Changes should have been applied
            expected = ["hello there", "general kenobi"]
            for i in range(2):
                view = self.view.window().find_open_file(file_paths[i])
                self.assertTrue(view)
                view.set_scratch(True)
                self.assertTrue(view.is_valid())
                self.assertFalse(view.is_loading())
                self.assertEqual(view.substr(sublime.Region(0, view.size())), expected[i])
                view.close()

    def test_m_workspace_applyEdit_with_wrong_uri(self) -> Generator:
        uri = "file:///C:/wrong/uri.txt"
        yield from verify(
            self,
            "workspace/applyEdit",
            {
                "edit": {
                    "documentChanges": [
                        {
                            "textDocument": {
                                "uri": uri,
                                "version": None
                            },
                            "edits": [
                                {
                                    "range": {
                                        "start": {"line": 0, "character": 0},
                                        "end": {"line": 0, "character": 1}
                                    },
                                    "newText": "hello"
                                },
                                {
                                    "range": {
                                        "start": {"line": 0, "character": 2},
                                        "end": {"line": 0, "character": 3}
                                    },
                                    "newText": "there"
                                }
                            ]
                        }
                    ]
                }
            },
            {
                "applied": False,
                "failureReason": f"Failed to open URI {uri}",
                "failedChange": 0
            }
        )

    def test_m_workspace_applyEdit_with_wrong_document_version(self) -> Generator:
        with tempfile.TemporaryDirectory() as dirpath:
            file_name = os.path.join(dirpath, "file3.txt")
            uri = filename_to_uri(file_name)
            version = 123
            Path(file_name).write_text("a b", encoding="utf-8")
            yield from verify(
                self,
                "workspace/applyEdit",
                {
                    "edit": {
                        "documentChanges": [
                            {
                                "textDocument": {
                                    "uri": uri,
                                    "version": version
                                },
                                "edits": [
                                    {
                                        "range": {
                                            "start": {"line": 0, "character": 0},
                                            "end": {"line": 0, "character": 1}
                                        },
                                        "newText": "hello"
                                    },
                                    {
                                        "range": {
                                            "start": {"line": 0, "character": 2},
                                            "end": {"line": 0, "character": 3}
                                        },
                                        "newText": "there"
                                    }
                                ]
                            }
                        ]
                    }
                },
                {
                    "applied": False,
                    "failureReason": f"Document version for URI {uri} is 0, but required {version}",
                    "failedChange": 0
                }
            )

