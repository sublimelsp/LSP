from . import test_sublime as test_sublime
from .sessions import create_session
from .sessions import Session
from .test_mocks import MockClient
from .test_mocks import MockConfigs
from .test_mocks import MockSettings
from .test_mocks import MockView
from .test_mocks import MockWindow
from .test_mocks import TEST_CONFIG
from .test_mocks import TEST_LANGUAGE
from .types import ClientConfig
from .windows import WindowDocumentHandler
from os.path import basename
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

    def test_sends_did_open_to_session(self):
        view = MockView(__file__)
        window = MockWindow([[view]])
        view.set_window(window)
        handler = WindowDocumentHandler(test_sublime, MockSettings(), window, MockConfigs())
        client = MockClient()
        session = self.assert_if_none(
            create_session(TEST_CONFIG, "", dict(), MockSettings(),
                           bootstrap_client=client))
        handler.add_session(session)

        # open
        handler.handle_view_opened(view)
        self.assertTrue(handler.has_document_state(__file__))
        self.assertEqual(len(client._notifications), 1)
        did_open = client._notifications[0]
        document = did_open.params["textDocument"]
        self.assertEqual(document.get("languageId"), "test")
        self.assertEqual(document.get("text"), "asdf")
        self.assertEqual(document.get("version"), 0)
        self.assertEqual(view._status.get("lsp_clients"), "test")

        # change 1
        view._text = "asdf jklm"
        handler.handle_view_modified(view)
        changes = handler._pending_buffer_changes[view.buffer_id()]
        self.assertEqual(changes, dict(view=view, version=1))
        self.assertEqual(len(client._notifications), 1)

        # change 2
        view._text = "asdf jklm qwer"
        handler.handle_view_modified(view)
        changes = handler._pending_buffer_changes[view.buffer_id()]
        self.assertEqual(changes, dict(view=view, version=2))
        self.assertEqual(len(client._notifications), 1)

        # purge
        test_sublime._run_timeout()
        self.assertEqual(len(client._notifications), 2)
        did_change = client._notifications[1]
        document = did_change.params.get("textDocument")
        self.assertEqual(document.get("version"), 1)  # increments with did_change
        purged_changes = did_change.params["contentChanges"]
        self.assertEqual(purged_changes[0].get("text"), view._text)

        # save
        handler.handle_view_saved(view)
        self.assertEqual(len(client._notifications), 3)
        did_save = client._notifications[2]
        document = did_save.params.get("textDocument")
        self.assertIn(basename(__file__), document.get("uri"))

        # close
        handler.handle_view_closed(view)
        self.assertEqual(len(client._notifications), 4)
        did_close = client._notifications[3]
        document = did_close.params.get("textDocument")
        self.assertIn(basename(__file__), document.get("uri"))
        self.assertFalse(__file__ in handler._document_states)

    def test_sends_did_open_to_multiple_sessions(self):
        view = MockView(__file__)
        window = MockWindow([[view]])
        view.set_window(window)
        handler = WindowDocumentHandler(test_sublime, MockSettings(), window, MockConfigs())
        client = MockClient()
        session = self.assert_if_none(
            create_session(TEST_CONFIG, "", dict(), MockSettings(),
                           bootstrap_client=client))
        client2 = MockClient()
        test_config2 = ClientConfig("test2", [], None, languages=[TEST_LANGUAGE])
        session2 = self.assert_if_none(
            create_session(test_config2, "", dict(), MockSettings(),
                           bootstrap_client=client2))

        handler.add_session(session)
        handler.add_session(session2)
        handler.handle_view_opened(view)
        self.assertTrue(handler.has_document_state(__file__))
        self.assertEqual(len(client._notifications), 1)
        self.assertEqual(len(client2._notifications), 1)

        did_open = client._notifications[0]
        document = did_open.params["textDocument"]
        self.assertEqual(document.get("languageId"), "test")
        self.assertEqual(document.get("text"), "asdf")
        self.assertEqual(document.get("version"), 0)

        did_open2 = client._notifications[0]
        document2 = did_open2.params["textDocument"]
        self.assertEqual(document2.get("languageId"), "test")
        self.assertEqual(document2.get("text"), "asdf")
        self.assertEqual(document2.get("version"), 0)
        status_string = view._status.get("lsp_clients")
        if status_string:
            status_configs = status_string.split(", ")
            self.assertIn("test", status_configs)
            self.assertIn("test2", status_configs)
