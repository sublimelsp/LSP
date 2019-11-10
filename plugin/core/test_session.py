from .types import ClientConfig, ClientStates, Settings
from .sessions import create_session, Session
from .protocol import Request, Notification
from .logging import debug
from .test_mocks import MockWindow
from .test_mocks import test_config
from .test_mocks import test_language
from .test_mocks import test_workspaces

import unittest
import unittest.mock
try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional and Session
except ImportError:
    pass


basic_responses = {
    'initialize': {
        'capabilities': {
            'testing': True,
            'hoverProvider': True,
            'completionProvider': {
                'triggerCharacters': ['.'],
                'resolveProvider': False
            },
            'textDocumentSync': True,
            'definitionProvider': True,
            'typeDefinitionProvider': True,
            'declarationProvider': True,
            'implementationProvider': True
        }
    }
}


class MockClient():
    def __init__(self, async_response=None) -> None:
        self.responses = basic_responses
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

    def send_response(self, request, request_id, params) -> None:
        pass

    def set_error_display_handler(self, handler: 'Callable') -> None:
        pass

    def set_crash_handler(self, handler: 'Callable') -> None:
        pass

    def exit(self) -> None:
        pass


class SessionTest(unittest.TestCase):

    def assert_if_none(self, session) -> 'Session':
        self.assertIsNotNone(session)
        return session

    # @unittest.skip("need an example config")
    def test_can_create_session(self):

        config = ClientConfig(name="test", binary_args=["ls"], tcp_port=None, languages=[test_language])
        session = self.assert_if_none(
            create_session(
                window=MockWindow(),
                config=config,
                workspaces=test_workspaces,
                env=dict(),
                settings=Settings()))
        self.assertEqual(session.state, ClientStates.STARTING)
        session.end()
        # self.assertIsNone(session.capabilities) -- empty dict

    def test_can_get_started_session(self):
        post_initialize_callback = unittest.mock.Mock()
        session = self.assert_if_none(
            create_session(window=MockWindow(),
                           config=test_config,
                           workspaces=test_workspaces,
                           env=dict(),
                           settings=Settings(),
                           bootstrap_client=MockClient(),
                           on_post_initialize=post_initialize_callback))
        self.assertEqual(session.state, ClientStates.READY)
        self.assertIsNotNone(session.client)
        self.assertTrue(session.has_capability("testing"))
        self.assertTrue(session.get_capability("testing"))
        post_initialize_callback.assert_called_once()

    def test_pre_initialize_callback_is_invoked(self):
        pre_initialize_callback = unittest.mock.Mock()
        post_initialize_callback = unittest.mock.Mock()
        session = self.assert_if_none(
            create_session(window=MockWindow(),
                           config=test_config,
                           workspaces=test_workspaces,
                           env=dict(),
                           settings=Settings(),
                           bootstrap_client=MockClient(),
                           on_pre_initialize=pre_initialize_callback,
                           on_post_initialize=post_initialize_callback))
        self.assertEqual(session.state, ClientStates.READY)
        self.assertIsNotNone(session.client)
        self.assertTrue(session.has_capability("testing"))
        self.assertTrue(session.get_capability("testing"))
        pre_initialize_callback.assert_called_once()
        post_initialize_callback.assert_called_once()

    def test_can_shutdown_session(self):
        post_initialize_callback = unittest.mock.Mock()
        post_exit_callback = unittest.mock.Mock()
        session = self.assert_if_none(
            create_session(window=MockWindow(),
                           config=test_config,
                           workspaces=test_workspaces,
                           env=dict(),
                           settings=Settings(),
                           bootstrap_client=MockClient(),
                           on_post_initialize=post_initialize_callback,
                           on_post_exit=post_exit_callback))
        self.assertEqual(session.state, ClientStates.READY)
        self.assertIsNotNone(session.client)
        self.assertTrue(session.has_capability("testing"))
        post_initialize_callback.assert_called_once()
        session.end()
        self.assertEqual(session.state, ClientStates.STOPPING)
        self.assertIsNone(session.client)
        self.assertFalse(session.has_capability("testing"))
        self.assertIsNone(session.get_capability("testing"))
        post_exit_callback.assert_called_once()
