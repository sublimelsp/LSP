from LSP.plugin.core.protocol import ErrorCode
from LSP.plugin.core.protocol import TextDocumentSyncKindFull
from LSP.plugin.core.protocol import TextDocumentSyncKindIncremental
from LSP.plugin.core.typing import Any, Dict, Generator, Optional
from LSP.plugin.core.url import filename_to_uri
from setup import TextDocumentTestCase
import os
import sublime
import tempfile


class ServerRequests(TextDocumentTestCase):

    def verify(self, method: str, input_params: Any, expected_output_params: Any) -> Generator:
        promise = self.make_server_do_fake_request(method, input_params)
        yield from self.await_promise(promise)
        self.assertEqual(promise.result(), expected_output_params)

    def test_unknown_method(self) -> Generator:
        yield from self.verify("foobar/qux", {}, {"code": ErrorCode.MethodNotFound, "message": "foobar/qux"})

    def test_m_workspace_workspaceFolders(self) -> Generator:
        expected_output = [{"name": os.path.basename(f), "uri": filename_to_uri(f)}
                           for f in sublime.active_window().folders()]
        self.maxDiff = None
        yield from self.verify("workspace/workspaceFolders", {}, expected_output)

    def test_m_workspace_configuration(self) -> Generator:
        self.session.config.settings.set("foo.bar", "$hello")
        self.session.config.settings.set("foo.baz", "$world")
        self.session.config.settings.set("foo.a", 1)
        self.session.config.settings.set("foo.b", None)
        self.session.config.settings.set("foo.c", ["asdf ${hello} ${world}"])

        class TempPlugin:

            @classmethod
            def additional_variables(cls) -> Optional[Dict[str, str]]:
                return {"hello": "X", "world": "Y"}

        self.session._plugin_class = TempPlugin  # type: ignore
        method = "workspace/configuration"
        params = {"items": [{"section": "foo"}]}
        expected_output = [{"bar": "X", "baz": "Y", "a": 1, "b": None, "c": ["asdf X Y"]}]
        yield from self.verify(method, params, expected_output)
        self.session.config.settings.clear()

    def test_m_workspace_applyEdit(self) -> Generator:
        old_change_count = self.insert_characters("hello\nworld\n")
        edit = {
            "newText": "there",
            "range": {"start": {"line": 1, "character": 0}, "end": {"line": 1, "character": 5}}}
        params = {"edit": {"changes": {filename_to_uri(self.view.file_name()): [edit]}}}
        yield from self.verify("workspace/applyEdit", params, {"applied": True})
        yield lambda: self.view.change_count() > old_change_count
        self.assertEqual(self.view.substr(sublime.Region(0, self.view.size())), "hello\nthere\n")

    def test_m_workspace_applyEdit_with_nontrivial_promises(self) -> Generator:
        with tempfile.TemporaryDirectory() as dirpath:
            initial_text = ["a b", "c d"]
            file_paths = []
            for i in range(0, 2):
                file_paths.append(os.path.join(dirpath, "file{}.txt".format(i)))
                with open(file_paths[-1], "w") as fp:
                    fp.write(initial_text[i])
            yield from self.verify(
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
            for i in range(0, 2):
                view = self.view.window().find_open_file(file_paths[i])
                self.assertTrue(view)
                view.set_scratch(True)
                self.assertTrue(view.is_valid())
                self.assertFalse(view.is_loading())
                self.assertEqual(view.substr(sublime.Region(0, view.size())), expected[i])
                view.close()

    def test_m_client_registerCapability(self) -> Generator:
        yield from self.verify(
            "client/registerCapability",
            {
                "registrations":
                [
                    {"method": "foo/bar", "id": "hello"},
                    {"method": "bar/baz", "id": "world", "registerOptions": {"frobnicatable": True}},
                    {"method": "workspace/didChangeWorkspaceFolders", "id": "asdf"},
                    {"method": "textDocument/didOpen", "id": "1"},
                    {"method": "textDocument/willSaveWaitUntil", "id": "2",
                     "registerOptions": {"documentSelector": [{"language": "txt"}]}},
                    {"method": "textDocument/didChange", "id": "adsf",
                     "registerOptions": {"syncKind": TextDocumentSyncKindFull, "documentSelector": [
                       {"language": "txt"}
                     ]}},
                    {"method": "textDocument/completion", "id": "myCompletionRegistrationId",
                     "registerOptions": {"triggerCharacters": ["!", "@", "#"], "documentSelector": [
                       {"language": "txt"}
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
        self.assertFalse(self.session.capabilities.get("textDocumentSync.willSaveWaitUntil"))
        sb = next(self.session.session_buffers_async())
        self.assertEqual(sb.capabilities.text_sync_kind(), TextDocumentSyncKindFull)
        self.assertEqual(sb.capabilities.get("textDocumentSync.willSaveWaitUntil"), {"id": "2"})
        self.assertEqual(self.session.capabilities.text_sync_kind(), TextDocumentSyncKindIncremental)

        # Check that textDocument/completion was registered onto the SessionBuffer, and check that the trigger
        # characters for each view were updated
        self.assertEqual(sb.capabilities.get("completionProvider.id"), "myCompletionRegistrationId")
        self.assertEqual(sb.capabilities.get("completionProvider.triggerCharacters"), ["!", "@", "#"])
        self.assertTrue(len(sb.session_views) > 0)
        for sv in sb.session_views:
            found = False
            triggers = sv.view.settings().get("auto_complete_triggers")
            for trigger in triggers:
                if "server" in trigger and "registration_id" in trigger:
                    self.assertEqual(trigger.get("characters"), "!@#")
                    found = True
            self.assertTrue(found)

    def test_m_client_unregisterCapability(self) -> Generator:
        yield from self.verify(
            "client/registerCapability",
            {"registrations": [{"method": "foo/bar", "id": "hello"}]},
            None)
        self.assertIn("barProvider", self.session.capabilities)
        yield from self.verify(
            "client/unregisterCapability",
            {"unregisterations": [{"method": "foo/bar", "id": "hello"}]},
            None)
        self.assertNotIn("barProvider", self.session.capabilities)
