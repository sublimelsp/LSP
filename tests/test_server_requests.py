from __future__ import annotations

from .setup import TextDocumentTestCase
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.url import filename_to_uri
from LSP.protocol import ErrorCodes
from LSP.protocol import TextDocumentSyncKind
from typing import Any
from typing import Generator
from typing import TYPE_CHECKING
import os
import sublime

if TYPE_CHECKING:
    from LSP.plugin.core.sessions import SessionBufferProtocol


def get_auto_complete_trigger(sb: SessionBufferProtocol) -> list[dict[str, str]] | None:
    for sv in sb.session_views:
        triggers = sv.view.settings().get("auto_complete_triggers")
        for trigger in triggers:
            if "server" in trigger and "registration_id" in trigger:
                return trigger
    return None


def verify(testcase: TextDocumentTestCase, method: str, input_params: Any, expected_output_params: Any) -> Generator:
    promise = testcase.make_server_do_fake_request(method, input_params)
    yield from testcase.await_promise(promise)
    testcase.assertEqual(promise.result(), expected_output_params)


class ServerRequests(TextDocumentTestCase):

    def test_unknown_method(self) -> Generator:
        yield from verify(self, "foobar/qux", {}, {"code": ErrorCodes.MethodNotFound, "message": "foobar/qux"})

    def test_m_workspace_workspaceFolders(self) -> Generator:
        expected_output = [{"name": os.path.basename(f), "uri": filename_to_uri(f)}
                           for f in sublime.active_window().folders()]
        self.maxDiff = None
        yield from verify(self, "workspace/workspaceFolders", {}, expected_output)

    def test_m_workspace_configuration(self) -> Generator:
        self.session.config.settings.set("foo.bar", "$hello")
        self.session.config.settings.set("foo.baz", "$world")
        self.session.config.settings.set("foo.a", 1)
        self.session.config.settings.set("foo.b", None)
        self.session.config.settings.set("foo.c", ["asdf ${hello} ${world}"])
        self.session._variables.update({"hello": "X", "world": "Y"})
        method = "workspace/configuration"
        params = {"items": [{"section": "foo"}]}
        expected_output = [{"bar": "X", "baz": "Y", "a": 1, "b": None, "c": ["asdf X Y"]}]
        yield from verify(self, method, params, expected_output)
        self.session.config.settings.clear()

    def test_m_client_registerCapability(self) -> Generator:
        yield from verify(
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
        sb = next(self.session.session_buffers_async())
        self.assertEqual(sb.capabilities.text_sync_kind(), TextDocumentSyncKind.Full)
        self.assertEqual(sb.capabilities.get("textDocumentSync.willSaveWaitUntil"), {"id": "2"})
        self.assertEqual(self.session.capabilities.text_sync_kind(), TextDocumentSyncKind.Incremental)

        # Check that textDocument/completion was registered onto the SessionBuffer, and check that the trigger
        # characters for each view were updated
        self.assertEqual(sb.capabilities.get("completionProvider.id"), "myCompletionRegistrationId")
        self.assertEqual(sb.capabilities.get("completionProvider.triggerCharacters"), ["!", "@", "#"])
        trigger = get_auto_complete_trigger(sb)
        self.assertTrue(trigger)
        self.assertEqual(trigger.get("characters"), "!@#")

    def test_m_client_unregisterCapability(self) -> Generator:
        yield from verify(
            self,
            "client/registerCapability",
            {"registrations": [{"method": "foo/bar", "id": "hello"}]},
            None)
        self.assertIn("barProvider", self.session.capabilities)
        yield from verify(
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

    def test_m_client_registerCapability(self) -> Generator:
        yield from verify(
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
