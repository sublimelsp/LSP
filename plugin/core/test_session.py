from .types import ClientConfig, LanguageConfig, ClientStates, Settings
from .sessions import create_session, Session
from .protocol import Request, Notification
from .logging import debug

import unittest
import unittest.mock
try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional and Session
except ImportError:
    pass


completion_provider = {
    'triggerCharacters': ['.'],
    'resolveProvider': False
}


class MockClient():
    def __init__(self, async_response=None) -> None:
        self.responses = {
            'initialize': {"capabilities": dict(testing=True, hoverProvider=True,
                                                completionProvider=completion_provider, textDocumentSync=True)},
        }  # type: dict
        self._notifications = []  # type: List[Notification]
        self._async_response_callback = async_response

    def send_request(self, request: Request, on_success: 'Callable', on_error: 'Callable' = None) -> None:
        response = self.responses.get(request.method)
        debug("TEST: responding to", request.method, "with", response)
        if self._async_response_callback:
            self._async_response_callback(lambda: on_success(response))
        else:
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

    def exit(self) -> None:
        pass


test_language = LanguageConfig("test", ["source.test"], ["Plain Text"])
test_config = ClientConfig("test", [], None, languages=[test_language])


class SessionTest(unittest.TestCase):

    def assert_if_none(self, session) -> 'Session':
        self.assertIsNotNone(session)
        return session

    # @unittest.skip("need an example config")
    def test_can_create_session(self):

        config = ClientConfig("test", ["ls"], None, [test_language])
        project_path = "/"
        session = self.assert_if_none(
            create_session(config, project_path, dict(), Settings()))

        self.assertEqual(session.state, ClientStates.STARTING)
        self.assertEqual(session.project_path, project_path)
        session.end()
        # self.assertIsNone(session.capabilities) -- empty dict

    def test_can_get_started_session(self):
        project_path = "/"
        created_callback = unittest.mock.Mock()
        session = self.assert_if_none(
            create_session(test_config, project_path, dict(), Settings(),
                           bootstrap_client=MockClient(),
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
                           bootstrap_client=MockClient(),
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
