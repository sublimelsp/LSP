from . import test_sublime as test_sublime
from .diagnostics import DiagnosticsStorage
from .sessions import create_session
from .sessions import Session
from .test_mocks import MockClient
from .test_mocks import MockConfigs
from .test_mocks import MockDocuments
from .test_mocks import MockHandlerDispatcher
from .test_mocks import MockSettings
from .test_mocks import MockView
from .test_mocks import MockWindow
from .test_mocks import TEST_CONFIG
from .test_mocks import TestDocumentHandlerFactory
from .test_mocks import TestGlobalConfigs
from .types import ClientConfig
from .types import LanguageConfig
from .windows import WindowManager
from .windows import WindowRegistry
import tempfile
import unittest

try:
    from typing import Callable, List, Optional, Set, Dict, Any, Tuple
    assert Callable and List and Optional and Set and Session and Dict and Any and Tuple
    assert ClientConfig and LanguageConfig
except ImportError:
    pass


def mock_start_session(window: MockWindow,
                       project_path: str,
                       config: ClientConfig,
                       on_pre_initialize: 'Callable[[Session], None]',
                       on_post_initialize: 'Callable[[Session], None]',
                       on_post_exit: 'Callable[[str], None]') -> 'Optional[Session]':
    return create_session(
        config=TEST_CONFIG,
        project_path=project_path,
        env=dict(),
        settings=MockSettings(),
        bootstrap_client=MockClient(),
        on_pre_initialize=on_pre_initialize,
        on_post_initialize=on_post_initialize,
        on_post_exit=on_post_exit)


class WindowRegistryTests(unittest.TestCase):

    def test_can_get_window_state(self):
        windows = WindowRegistry(TestGlobalConfigs(), TestDocumentHandlerFactory(),
                                 mock_start_session,
                                 test_sublime, MockHandlerDispatcher())
        test_window = MockWindow()
        wm = windows.lookup(test_window)
        self.assertIsNotNone(wm)

    def test_removes_window_state(self):
        test_window = MockWindow([[MockView(__file__)]])
        windows = WindowRegistry(TestGlobalConfigs(), TestDocumentHandlerFactory(),
                                 mock_start_session,
                                 test_sublime, MockHandlerDispatcher())
        wm = windows.lookup(test_window)
        wm.start_active_views()

        self.assertIsNotNone(wm)

        # closing views triggers window unload detection
        test_window.close()
        wm.handle_view_closed(MockView(__file__))
        test_sublime._run_timeout()

        self.assertEqual(len(windows._windows), 0)


class WindowManagerTests(unittest.TestCase):

    def test_can_start_active_views(self):
        docs = MockDocuments()
        wm = WindowManager(MockWindow([[MockView(__file__)]]), MockConfigs(), docs,
                           DiagnosticsStorage(None), mock_start_session, test_sublime, MockHandlerDispatcher())
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name))
        self.assertListEqual(docs._documents, [__file__])

    def test_can_open_supported_view(self):
        docs = MockDocuments()
        window = MockWindow([[]])
        wm = WindowManager(window, MockConfigs(), docs, DiagnosticsStorage(None), mock_start_session, test_sublime,
                           MockHandlerDispatcher())

        wm.start_active_views()
        self.assertIsNone(wm.get_session(TEST_CONFIG.name))
        self.assertListEqual(docs._documents, [])

        # session must be started (todo: verify session is ready)
        view = MockView(__file__)

        # WindowManager will call window.active_view() at some point during wm.activate_view
        window._files_in_groups = [[view]]

        wm.activate_view(view)
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name))
        self.assertEqual(len(docs._sessions), 1)

    def test_can_restart_sessions(self):
        docs = MockDocuments()
        wm = WindowManager(MockWindow([[MockView(__file__)]]), MockConfigs(), docs,
                           DiagnosticsStorage(None), mock_start_session, test_sublime, MockHandlerDispatcher())
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        wm.restart_sessions()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

    def test_ends_sessions_when_closed(self):
        docs = MockDocuments()
        test_window = MockWindow([[MockView(__file__)]])
        wm = WindowManager(test_window, MockConfigs(), docs,
                           DiagnosticsStorage(None), mock_start_session, test_sublime, MockHandlerDispatcher())
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        # closing views triggers window unload detection
        test_window.close()
        wm.handle_view_closed(MockView(__file__))
        test_sublime._run_timeout()
        self.assertEqual(len(wm._sessions), 0)
        self.assertEqual(len(docs._sessions), 0)

    def test_ends_sessions_when_quick_switching(self):
        docs = MockDocuments()
        test_window = MockWindow([[MockView(__file__)]])
        wm = WindowManager(test_window, MockConfigs(), docs,
                           DiagnosticsStorage(None), mock_start_session, test_sublime, MockHandlerDispatcher())
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        # change project_path
        new_project_path = tempfile.gettempdir()
        test_window.set_folders([new_project_path])
        another_view = MockView(None)
        another_view.settings().set("syntax", "Unsupported Syntax")
        test_window._files_in_groups[0][0] = another_view
        wm.activate_view(another_view)

        self.assertEqual(len(wm._sessions), 0)
        self.assertEqual(len(docs._sessions), 0)

        # don't forget to check or we'll keep restarting sessions!
        self.assertEqual(wm.get_project_path(), new_project_path)

    def test_offers_restart_on_crash(self):
        docs = MockDocuments()
        wm = WindowManager(MockWindow([[MockView(__file__)]]), MockConfigs(), docs,
                           DiagnosticsStorage(None), mock_start_session, test_sublime,
                           MockHandlerDispatcher())
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        wm._handle_server_crash(TEST_CONFIG)

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

    def test_invokes_language_handler(self):
        docs = MockDocuments()
        dispatcher = MockHandlerDispatcher()
        wm = WindowManager(MockWindow([[MockView(__file__)]]), MockConfigs(), docs,
                           DiagnosticsStorage(None), mock_start_session, test_sublime,
                           dispatcher)
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        # client_start_listeners, client_initialization_listeners,
        self.assertTrue(TEST_CONFIG.name in dispatcher._initialized)
