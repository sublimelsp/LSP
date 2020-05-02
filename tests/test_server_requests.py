from LSP.plugin.core.protocol import ErrorCode
from LSP.plugin.core.typing import Any, Generator
from LSP.plugin.core.url import filename_to_uri
from setup import TextDocumentTestCase
import sublime


class ServerRequests(TextDocumentTestCase):

    def verify(self, method: str, input_params: Any, expected_output_params: Any) -> Generator:
        promise = self.make_server_do_fake_request(method, input_params)
        yield from self.await_promise(promise)
        self.assertEqual(promise.result(), expected_output_params)

    def test_unknown_method(self) -> Generator:
        yield from self.verify("foobar/qux", {}, {"code": ErrorCode.MethodNotFound, "message": "foobar/qux"})

    def test_m_workspace_workspaceFolders(self) -> Generator:
        uri = filename_to_uri(sublime.active_window().folders()[0])
        yield from self.verify("workspace/workspaceFolders", {}, [{"name": "LSP", "uri": uri}])

    def test_m_workspace_configuration(self) -> Generator:
        yield from self.verify("workspace/configuration", {}, [])

    def test_m_workspace_applyEdit(self) -> Generator:
        old_change_count = self.insert_characters("hello\nworld\n")
        edit = {
            "newText": "there",
            "range": {"start": {"line": 1, "character": 0}, "end": {"line": 1, "character": 5}}}
        params = {"edit": {"changes": {filename_to_uri(self.view.file_name()): [edit]}}}
        yield from self.verify("workspace/applyEdit", params, {"applied": True})
        yield lambda: self.view.change_count() > old_change_count
        self.assertEqual(self.view.substr(sublime.Region(0, self.view.size())), "hello\nthere\n")

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
                     "registerOptions": {"documentSelector": {}}}  # TODO: DocumentSelector someday?
                ]
            },
            None)
        self.assertIn("barProvider", self.session.capabilities)
        self.assertEqual(self.session.capabilities["barProvider"]["id"], "hello")
        self.assertIn("bazProvider", self.session.capabilities)
        self.assertEqual(self.session.capabilities["bazProvider"], {"id": "world", "frobnicatable": True})
        self.assertEqual(self.session.capabilities["workspace"]["workspaceFolders"]["changeNotifications"], "asdf")
        self.assertEqual(self.session.capabilities["textDocumentSync"]["openClose"], {"id": "1"})
        self.assertEqual(self.session.capabilities["textDocumentSync"]["willSaveWaitUntil"],
                         {"id": "2", "documentSelector": {}})

    def test_m_client_unregisterCapability(self) -> Generator:
        yield from self.verify(
            "client/registerCapability",
            {"registrations": [{"method": "foo/bar", "id": "hello"}]},
            None)
        self.assertIn("barProvider", self.session.capabilities)
        yield from self.verify(
            "client/unregisterCapability",
            {"unregisterations": [{"method": "foo/bar", "id": "asdf"}]},  # the ID doesn't matter for us (?)
            None)
        self.assertNotIn("barProvider", self.session.capabilities)
