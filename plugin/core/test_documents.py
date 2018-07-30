import unittest
from .events import Events
from .windows import WindowDocumentHandler
from .sessions import create_session
from .test_windows import TestWindow, TestView
from .test_session import test_config, TestClient
import unittest.mock
from . import test_sublime as test_sublime
from .test_rpc import TestSettings

try:
    from typing import Any, Dict
    assert Any and Dict
except ImportError:
    pass


class WindowDocumentHandlerTests(unittest.TestCase):

    def test_sends_did_open_to_session(self):

        events = Events()
        view = TestView(__file__)
        window = TestWindow([[view]])
        view.set_window(window)
        handler = WindowDocumentHandler(test_sublime, TestSettings(), window, events)
        client = TestClient()
        session = create_session(test_config, "", dict(), TestSettings(),
                                 bootstrap_client=client)
        handler.add_session(session)
        events.publish("view.on_activated_async", view)
        self.assertTrue(handler.has_document_state(__file__))
        self.assertEqual(len(client._notifications), 1)

    def test_ignores_views_from_other_window(self):
        events = Events()
        window = TestWindow()
        view = TestView(__file__)
        handler = WindowDocumentHandler(test_sublime, TestSettings(), window, events)
        client = TestClient()
        session = create_session(test_config, "", dict(), TestSettings(),
                                 bootstrap_client=client)
        handler.add_session(session)
        events.publish("view.on_activated_async", view)
        self.assertFalse(handler.has_document_state(__file__))
        self.assertEqual(len(client._notifications), 0)
