from .windows import WindowManager, WindowRegistry
from .diagnostics import WindowDiagnostics
from .sessions import create_session, Session
from .test_session import MockClient, test_config
from .test_rpc import MockSettings
from .events import global_events
from .types import ClientConfig
from . import test_sublime as test_sublime
from .workspace import Workspace
from .url import filename_to_uri
import tempfile
import unittest
from .test_mocks import MockDocuments
from .test_mocks import MockHandlerDispatcher
from .test_mocks import MockView
from .test_mocks import MockWindow
from .test_mocks import TestDocumentHandlerFactory
from .test_mocks import TestGlobalConfigs
from .test_mocks import MockConfigs

try:
    from .types import WindowLike
    from .types import ViewLike
    from typing import Callable, List, Optional, Set, Dict, Any, Tuple, Iterable
    assert Callable and List and Optional and Set and Session and Dict and Any and Tuple and Iterable
    assert ClientConfig
    assert Workspace
    assert WindowLike
    assert ViewLike
except ImportError:
    pass


def mock_start_window_config(
    window: 'WindowLike',
    workspaces: 'Optional[Iterable[Workspace]]',
    _: 'ClientConfig',
    on_pre_initialize: 'Callable[[Session], None]',
    on_post_initialize: 'Callable[[Session], None]',
    on_post_exit: 'Callable[[str], None]'
) -> 'Optional[Session]':
    return create_session(
        window=window,
        config=test_config,
        workspaces=workspaces,
        env=dict(),
        settings=MockSettings(),
        bootstrap_client=MockClient(),
        on_pre_initialize=on_pre_initialize,
        on_post_initialize=on_post_initialize,
        on_post_exit=on_post_exit)


class WindowRegistryTests(unittest.TestCase):

    def make_window_registry(self) -> 'WindowRegistry':
        return WindowRegistry(
            TestGlobalConfigs(),
            TestDocumentHandlerFactory(),
            mock_start_window_config,
            test_sublime,
            MockHandlerDispatcher())

    def test_can_get_window_state(self):
        windows = self.make_window_registry()
        test_window = MockWindow()
        wm = windows.lookup(test_window)
        self.assertIsNotNone(wm)

    def test_removes_window_state(self):
        global_events.reset()
        test_window = MockWindow([[MockView(__file__)]])
        windows = self.make_window_registry()
        # import pdb; pdb.set_trace()
        wm = windows.lookup(test_window)
        wm.start_active_views()

        self.assertIsNotNone(wm)

        # closing views triggers window unload detection
        test_window.close()
        global_events.publish("view.on_close", MockView(__file__))
        test_sublime._run_timeout()

        self.assertEqual(len(windows._windows), 0)


class WindowManagerTests(unittest.TestCase):

    def make_window_manager(self, window: 'WindowLike') -> 'Tuple[WindowManager, MockDocuments]':
        docs = MockDocuments()
        window_manager = WindowManager(
            window,
            MockConfigs(),
            docs,
            WindowDiagnostics(),
            mock_start_window_config,
            test_sublime,
            MockHandlerDispatcher())
        return window_manager, docs

    def test_can_start_active_views(self):
        wm, docs = self.make_window_manager(MockWindow([[MockView(__file__)]]))
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))
        self.assertListEqual(docs._documents, [__file__])

    def test_can_open_supported_view(self):
        window = MockWindow([[]])
        wm, docs = self.make_window_manager(window)

        wm.start_active_views()
        self.assertIsNone(wm.get_session(test_config.name))
        self.assertListEqual(docs._documents, [])

        # session must be started (todo: verify session is ready)
        view = MockView(__file__)

        wm.activate_view(view)
        self.assertIsNotNone(wm.get_session(test_config.name))
        self.assertEqual(len(docs._sessions), 1)

    def test_can_restart_sessions(self):
        wm, docs = self.make_window_manager(MockWindow([[MockView(__file__)]]))
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        wm.restart_sessions()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

    def test_ends_sessions_when_closed(self):
        global_events.reset()
        docs = MockDocuments()
        test_window = MockWindow([[MockView(__file__)]])
        wm, docs = self.make_window_manager(test_window)
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        # closing views triggers window unload detection
        test_window.close()
        global_events.publish("view.on_close", MockView(__file__))
        test_sublime._run_timeout()
        self.assertEqual(len(wm._sessions), 0)
        self.assertEqual(len(docs._sessions), 0)

    def test_ends_sessions_when_quick_switching(self):
        global_events.reset()
        test_window = MockWindow([[MockView(__file__)]])
        wm, docs = self.make_window_manager(test_window)
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        # change workspaces
        new_project_path = tempfile.gettempdir()
        test_window.set_folders([new_project_path])
        # global_events.publish("view.on_close", MockView(__file__))
        another_view = MockView(None)
        another_view.settings().set("syntax", "Unsupported Syntax")
        wm.activate_view(another_view)

        self.assertEqual(len(wm._sessions), 0)
        self.assertEqual(len(docs._sessions), 0)

        # don't forget to check or we'll keep restarting sessions!
        self.assertIsNotNone(wm._workspaces)
        self.assertEqual(len(wm._workspaces), 1)
        self.assertEqual(wm._workspaces[0].uri, filename_to_uri(new_project_path))

    def test_offers_restart_on_crash(self):
        wm, docs = self.make_window_manager(MockWindow([[MockView(__file__)]]))
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        wm._handle_server_crash(test_config)

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

    def test_invokes_language_handler(self):
        docs = MockDocuments()
        dispatcher = MockHandlerDispatcher()
        wm = WindowManager(MockWindow([[MockView(__file__)]]), MockConfigs(), docs,
                           WindowDiagnostics(), mock_start_window_config, test_sublime,
                           dispatcher)
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        # client_start_listeners, client_initialization_listeners,
        self.assertTrue(test_config.name in dispatcher._initialized)
