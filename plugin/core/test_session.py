# from .rpc import (format_request, Client)
# from .protocol import (Request, Notification)
# from .clients import create_session, ClientConfig, ConfigState, ClientStates
from .types import ClientConfig, ClientStates, Settings
from .sessions import create_session, Session
from .protocol import Request, Notification

import unittest
import unittest.mock
# import json
try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional and Session
except ImportError:
    pass


class TestClient():
    def __init__(self) -> None:
        self.responses = {
            'initialize': {"capabilities": dict(testing=True, hoverProvider=True, textDocumentSync=True)},
            'textDocument/hover': {"contents": "greeting"}
        }  # type: dict
        self._notifications = []  # type: List[Notification]

    def send_request(self, request: Request, on_success: 'Callable', on_error: 'Callable'=None) -> None:
        response = self.responses.get(request.method)
        on_success(response)

    def send_notification(self, notification: Notification) -> None:
        self._notifications.append(notification)

    def on_notification(self, name, handler: 'Callable') -> None:
        pass

    def on_request(self, name, handler: 'Callable') -> None:
        pass

    def set_error_display_handler(self, handler: 'Callable') -> None:
        pass

    def set_crash_handler(self, handler: 'Callable') -> None:
        pass


test_config = ClientConfig("test", [], None, ["source.test"], ["Plain Text"], "test")


class SessionTest(unittest.TestCase):

    def assert_if_none(self, session) -> 'Session':
        self.assertIsNotNone(session)
        return session

    # @unittest.skip("need an example config")
    def test_can_create_session(self):
        config = ClientConfig("test", ["ls"], None, ["source.test"], ["Test.sublime-syntax"], "test")
        project_path = "/"
        session = self.assert_if_none(
            create_session(config, project_path, dict(), Settings()))

        self.assertEqual(session.state, ClientStates.STARTING)
        self.assertEqual(session.project_path, project_path)
        # self.assertIsNone(session.capabilities) -- empty dict

    def test_can_get_started_session(self):
        project_path = "/"
        created_callback = unittest.mock.Mock()
        session = self.assert_if_none(
            create_session(test_config, project_path, dict(), Settings(),
                           bootstrap_client=TestClient(),
                           on_created=created_callback))

        self.assertEqual(session.state, ClientStates.READY)
        self.assertIsNotNone(session.client)
        self.assertEqual(session.project_path, project_path)
        self.assertTrue(session.has_capability("testing"))
        self.assertTrue(session.get_capability("testing"))
        created_callback.assert_called_once()

    def test_can_shutdown_session(self):
        project_path = "/"
        created_callback = unittest.mock.Mock()
        ended_callback = unittest.mock.Mock()
        session = self.assert_if_none(
            create_session(test_config, project_path, dict(), Settings(),
                           bootstrap_client=TestClient(),
                           on_created=created_callback,
                           on_ended=ended_callback))

        self.assertEqual(session.state, ClientStates.READY)
        self.assertIsNotNone(session.client)
        self.assertEqual(session.project_path, project_path)
        self.assertTrue(session.has_capability("testing"))
        created_callback.assert_called_once()

        session.end()
        self.assertEqual(session.state, ClientStates.STOPPING)
        self.assertEqual(session.project_path, project_path)
        self.assertIsNone(session.client)
        self.assertFalse(session.has_capability("testing"))
        self.assertIsNone(session.get_capability("testing"))
        ended_callback.assert_called_once()
