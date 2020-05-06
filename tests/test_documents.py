from LSP.plugin.core.protocol import WorkspaceFolder
from LSP.plugin.core.sessions import create_session
from LSP.plugin.core.sessions import Session
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.windows import WindowDocumentHandler
from LSP.plugin.core.workspace import ProjectFolders
from os.path import basename
from test_mocks import MockClient
from test_mocks import MockConfigs
from test_mocks import MockSettings
from test_mocks import MockView
from test_mocks import MockWindow
from test_mocks import TEST_CONFIG
from test_mocks import TEST_LANGUAGE
import test_sublime
import unittest
import unittest.mock

try:
    from typing import Any, Dict
    assert Any and Dict and Session
except ImportError:
    pass


class WindowDocumentHandlerTests(unittest.TestCase):

    def assert_if_none(self, session) -> 'Session':
        self.assertIsNotNone(session)
        return session

    def test_sends_did_open_to_multiple_sessions(self):
        view = MockView(__file__)
        window = MockWindow([[view]])
        project_path = "/"
        folders = [WorkspaceFolder.from_path(project_path)]
        view.set_window(window)
        workspace = ProjectFolders(window)
        configs = MockConfigs()
        handler = WindowDocumentHandler(test_sublime, MockSettings(), window, workspace, configs)
        client = MockClient()
        session = self.assert_if_none(
            create_session(TEST_CONFIG, folders, dict(), MockSettings(),
                           bootstrap_client=client))
        client2 = MockClient()
        test_config2 = ClientConfig(name="test2", binary_args=[], tcp_port=None, languages=[TEST_LANGUAGE])
        configs.all.append(test_config2)
        session2 = self.assert_if_none(
            create_session(test_config2, folders, dict(), MockSettings(),
                           bootstrap_client=client2))

        handler.add_session(session)
        handler.add_session(session2)
        handler.handle_did_open(view)
        self.assertTrue(handler.has_document_state(__file__))
        self.assertEqual(len(client._notifications), 1)
        self.assertEqual(len(client2._notifications), 1)

        did_open = client._notifications[0]
        document = did_open.params["textDocument"]
        self.assertEqual(document.get("languageId"), "test")
        self.assertEqual(document.get("text"), "asdf")
        self.assertIsNotNone(document.get("version"))

        did_open2 = client._notifications[0]
        document2 = did_open2.params["textDocument"]
        self.assertEqual(document2.get("languageId"), "test")
        self.assertEqual(document2.get("text"), "asdf")
        self.assertIsNotNone(document2.get("version"))
        status_string = view._status.get("lsp_clients")
        if status_string:
            status_configs = status_string.split(", ")
            self.assertIn("test", status_configs)
            self.assertIn("test2", status_configs)
            self.assertIn("test", status_configs)
            self.assertIn("test2", status_configs)
