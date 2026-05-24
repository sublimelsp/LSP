from __future__ import annotations

from .setup import close_test_view
from .setup import TextDocumentTestCase
from LSP.plugin import Error
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.url import filename_to_uri
from LSP.protocol import ErrorCodes
from LSP.protocol import TextDocumentSyncKind
from pathlib import Path
from typing import Any
from typing import TYPE_CHECKING
import asyncio
import os
import sublime
import tempfile

if TYPE_CHECKING:
    from LSP.plugin.core.sessions import SessionBufferProtocol


def get_auto_complete_trigger(sb: SessionBufferProtocol) -> list[dict[str, str]] | None:
    for sv in sb.session_views:
        triggers = sv.view.settings().get("auto_complete_triggers")
        for trigger in triggers:
            if "server" in trigger and "registration_id" in trigger:
                return trigger
    return None


async def verify(
    testcase: TextDocumentTestCase,
    method: str,
    input_params: Any,
    expected_output_params: Any,
    expected_error_code: ErrorCodes | None = None,
) -> None:
    try:
        result = await testcase.make_server_do_fake_request(method, input_params)
        testcase.assertEqual(result, expected_output_params)
    except Error as error:
        if expected_error_code is not None:
            testcase.assertEqual(error.code, expected_error_code)
        else:
            testcase.fail(f"method {method} returned error {error}")


class ServerRequests(TextDocumentTestCase):
    async def test_unknown_method(self) -> None:
        await verify(
            self,
            "foobar/qux",
            {},
            {"code": ErrorCodes.MethodNotFound, "message": "foobar/qux"},
            ErrorCodes.MethodNotFound,
        )

    async def test_m_workspace_workspaceFolders(self) -> None:
        expected_output = [{"name": os.path.basename(f), "uri": filename_to_uri(f)}
                           for f in sublime.active_window().folders()]
        self.maxDiff = None
        await verify(self, "workspace/workspaceFolders", {}, expected_output)

    async def test_m_workspace_configuration(self) -> None:
        assert self.session
        self.session.config.settings.set("foo.bar", "$hello")
        self.session.config.settings.set("foo.baz", "$world")
        self.session.config.settings.set("foo.a", 1)
        self.session.config.settings.set("foo.b", None)
        self.session.config.settings.set("foo.c", ["asdf ${hello} ${world}"])
        self.session._variables.update({"hello": "X", "world": "Y"})
        method = "workspace/configuration"
        params = {"items": [{"section": "foo"}]}
        expected_output = [{"bar": "X", "baz": "Y", "a": 1, "b": None, "c": ["asdf X Y"]}]
        await verify(self, method, params, expected_output)
        self.session.config.settings.clear()

    async def test_m_workspace_applyEdit(self) -> None:
        old_change_count = self.insert_characters("hello\nworld\n")
        edit = {
            "newText": "there",
            "range": {"start": {"line": 1, "character": 0}, "end": {"line": 1, "character": 5}}}
        params = {"edit": {"changes": {filename_to_uri(self.view.file_name()): [edit]}}}
        await verify(self, "workspace/applyEdit", params, {"applied": True})
        while self.view.change_count() <= old_change_count:  # noqa: ASYNC110
            await asyncio.sleep(0.05)
        self.assertEqual(self.view.substr(sublime.Region(0, self.view.size())), "hello\nthere\n")

    async def test_m_workspace_applyEdit_with_nontrivial_promises(self) -> None:
        with tempfile.TemporaryDirectory() as dirpath:
            initial_text = ["a b", "c d"]
            file_paths = []
            for i in range(2):
                file_paths.append(os.path.join(dirpath, f"file{i}.txt"))
                Path(file_paths[-1]).write_text(initial_text[i], encoding="utf-8")  # noqa: ASYNC240
            await verify(
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
                await close_test_view(view)

    async def test_m_workspace_applyEdit_with_wrong_uri(self) -> None:
        uri = "file:///C:/wrong/uri.txt"
        await verify(
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

    async def test_m_workspace_applyEdit_with_wrong_document_version(self) -> None:
        uri = filename_to_uri(self.view.file_name())
        version = 123
        self.insert_characters("a b")
        await verify(
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
                "failureReason": f"Document version for URI {uri} is {self.view.change_count()}, but required {version}",  # noqa: E501
                "failedChange": 0
            }
        )

    async def test_m_client_registerCapability(self) -> None:
        await verify(
            self,
            "client/registerCapability",
            {
                "registrations":
                [
                    {"method": "foo/bar", "id": "hello"},
                    {"method": "bar/baz", "id": "world", "registerOptions": {"frobnicatable": True}},
                    {"method": "workspace/didChangeWorkspaceFolders", "id": "asdf"},
                    {"method": "textDocument/didOpen", "id": "1"},
                    {"method": "textDocument/willSaveWaitUntil", "id": "2",
                     "registerOptions": {"documentSelector": [{"language": "plaintext"}]}},
                    {"method": "textDocument/didChange", "id": "adsf",
                     "registerOptions": {"syncKind": TextDocumentSyncKind.Full, "documentSelector": [
                       {"language": "plaintext"}
                     ]}},
                    {"method": "textDocument/completion", "id": "myCompletionRegistrationId",
                     "registerOptions": {"triggerCharacters": ["!", "@", "#"], "documentSelector": [
                       {"language": "plaintext"}
                     ]}}
                ]
            },
            None)
        self.assertIn("barProvider", self.session.capabilities)
        self.assertEqual(self.session.capabilities.get("barProvider.id"), "hello")
        self.assertIn("bazProvider", self.session.capabilities)
        self.assertEqual(self.session.capabilities.get("bazProvider"), {"id": "world", "frobnicatable": True})
        self.assertEqual(self.session.capabilities.get("workspace.workspaceFolders.changeNotifications"), "asdf")
        self.assertEqual(self.session.capabilities.get("textDocumentSync.didOpen"), {"id": "1"})
        self.assertFalse(self.session.capabilities.get("textDocumentSync.didClose"))

        # willSaveWaitUntil is *only* registered on the buffer
        self.assertFalse(self.session.capabilities.get("textDocumentSync.willSaveWaitUntil"))
        await self.wait_until(lambda: len(list(self.session.session_buffers_async())) > 0)
        sb = next(self.session.session_buffers_async())
        await self.wait_until(lambda: sb.capabilities.text_sync_kind() == TextDocumentSyncKind.Full)
        self.assertEqual(sb.capabilities.get("textDocumentSync.willSaveWaitUntil"), {"id": "2"})
        self.assertEqual(self.session.capabilities.text_sync_kind(), TextDocumentSyncKind.Incremental)

        # Check that textDocument/completion was registered onto the SessionBuffer, and check that the trigger
        # characters for each view were updated
        self.assertEqual(sb.capabilities.get("completionProvider.id"), "myCompletionRegistrationId")
        self.assertEqual(sb.capabilities.get("completionProvider.triggerCharacters"), ["!", "@", "#"])
        await self.wait_until(lambda: get_auto_complete_trigger(sb) is not None)
        trigger = get_auto_complete_trigger(sb)
        self.assertEqual(trigger.get("characters"), "!@#")

    async def test_m_client_unregisterCapability(self) -> None:
        await verify(
            self,
            "client/registerCapability",
            {"registrations": [{"method": "foo/bar", "id": "hello"}]},
            None)
        self.assertIn("barProvider", self.session.capabilities)
        await verify(
            self,
            "client/unregisterCapability",
            {"unregisterations": [{"method": "foo/bar", "id": "hello"}]},
            None)
        self.assertNotIn("barProvider", self.session.capabilities)


class ServerRequestsWithAutoCompleteSelector(TextDocumentTestCase):

    @classmethod
    def get_stdio_test_config(cls) -> ClientConfig:
        return ClientConfig.from_config(
            super().get_stdio_test_config(),
            {
                "auto_complete_selector": "punctuation.section",
                "disabled_capabilities": {
                    "completionProvider": {
                        "triggerCharacters": True
                    }
                }
            }
        )

    async def test_m_client_registerCapability(self) -> None:
        await verify(
            self,
            "client/registerCapability",
            {
                "registrations":
                [
                    # Note that the triggerCharacters are disabled in the configuration.
                    {"method": "textDocument/completion", "id": "anotherCompletionRegistrationId",
                     "registerOptions": {"triggerCharacters": ["!", "@", "#"], "documentSelector": [
                       {"language": "plaintext"}
                     ]}}
                ]
            },
            None)
        sb = next(self.session.session_buffers_async())
        # Check that textDocument/completion was registered onto the SessionBuffer
        self.assertEqual(sb.capabilities.get("completionProvider.id"), "anotherCompletionRegistrationId")
        # Trigger characters should not have been registered
        self.assertFalse(sb.capabilities.get("completionProvider.triggerCharacters"))
        trigger = get_auto_complete_trigger(sb)
        self.assertTrue(trigger)
        # No triggers should have been assigned
        self.assertFalse(trigger.get("characters"))
        # The selector should have been set
        self.assertEqual(trigger.get("selector"), "punctuation.section")
