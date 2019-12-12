from .sessions import create_session, Session
from .test_mocks import MockClient
from .test_mocks import TEST_CONFIG
from .test_mocks import TEST_LANGUAGE
from .types import ClientConfig
from .types import ClientStates
from .types import Settings
import unittest
import unittest.mock

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional and Session
except ImportError:
    pass


class SessionTest(unittest.TestCase):

    def assert_if_none(self, session) -> 'Session':
        self.assertIsNotNone(session)
        return session

    # @unittest.skip("need an example config")
    def test_can_create_session(self):
        config = ClientConfig(
            name="test",
            binary_args=["ls"],
            tcp_port=None,
            scopes=[],
            languageId=None,
            languages=[TEST_LANGUAGE])
        project_path = "/"
        session = self.assert_if_none(
            create_session(config, project_path, dict(), Settings()))

        self.assertEqual(session.state, ClientStates.STARTING)
        session.end()
        # self.assertIsNone(session.capabilities) -- empty dict

    def test_can_get_started_session(self):
        project_path = "/"
        post_initialize_callback = unittest.mock.Mock()
        session = self.assert_if_none(
            create_session(config=TEST_CONFIG,
                           project_path=project_path,
                           env=dict(),
                           settings=Settings(),
                           bootstrap_client=MockClient(),
                           on_post_initialize=post_initialize_callback))
        self.assertEqual(session.state, ClientStates.READY)
        self.assertIsNotNone(session.client)
        self.assertTrue(session.has_capability("testing"))
        self.assertTrue(session.get_capability("testing"))
        assert post_initialize_callback.call_count == 1

    def test_pre_initialize_callback_is_invoked(self):
        project_path = "/"
        pre_initialize_callback = unittest.mock.Mock()
        post_initialize_callback = unittest.mock.Mock()
        session = self.assert_if_none(
            create_session(config=TEST_CONFIG,
                           project_path=project_path,
                           env=dict(),
                           settings=Settings(),
                           bootstrap_client=MockClient(),
                           on_pre_initialize=pre_initialize_callback,
                           on_post_initialize=post_initialize_callback))
        self.assertEqual(session.state, ClientStates.READY)
        self.assertIsNotNone(session.client)
        self.assertTrue(session.has_capability("testing"))
        self.assertTrue(session.get_capability("testing"))
        assert pre_initialize_callback.call_count == 1
        assert post_initialize_callback.call_count == 1

    def test_can_shutdown_session(self):
        project_path = "/"
        post_initialize_callback = unittest.mock.Mock()
        post_exit_callback = unittest.mock.Mock()
        session = self.assert_if_none(
            create_session(config=TEST_CONFIG,
                           project_path=project_path,
                           env=dict(),
                           settings=Settings(),
                           bootstrap_client=MockClient(),
                           on_post_initialize=post_initialize_callback,
                           on_post_exit=post_exit_callback))
        self.assertEqual(session.state, ClientStates.READY)
        self.assertIsNotNone(session.client)
        self.assertTrue(session.has_capability("testing"))
        assert post_initialize_callback.call_count == 1
        session.end()
        self.assertEqual(session.state, ClientStates.STOPPING)
        self.assertIsNone(session.client)
        self.assertFalse(session.has_capability("testing"))
        self.assertIsNone(session.get_capability("testing"))
        assert post_exit_callback.call_count == 1
