from LSP.plugin.core.diagnostics import DiagnosticsStorage
from LSP.plugin.core.sessions import create_session
from LSP.plugin.core.sessions import Session
from LSP.plugin.core.types import ClientConfig
from LSP.plugin.core.types import LanguageConfig
from LSP.plugin.core.windows import WindowManager
from LSP.plugin.core.windows import WindowRegistry
from LSP.plugin.core.workspace import ProjectFolders
from test_mocks import MockClient
from test_mocks import MockConfigs
from test_mocks import MockDocuments
from test_mocks import MockHandlerDispatcher
from test_mocks import MockSettings
from test_mocks import MockView
from test_mocks import MockWindow
from test_mocks import TEST_CONFIG
from test_mocks import TestDocumentHandlerFactory
from test_mocks import TestGlobalConfigs
import os
import tempfile
import test_sublime
import unittest

try:
    from LSP.plugin.core.protocol import WorkspaceFolder
    from typing import Callable, List, Optional, Set, Dict, Any, Tuple
    assert Callable and List and Optional and Set and Session and Dict and Any and Tuple
    assert ClientConfig and LanguageConfig and WorkspaceFolder
except ImportError:
    pass


def mock_start_session(window: MockWindow,
                       workspace_folders: 'List[WorkspaceFolder]',
                       config: ClientConfig,
                       on_pre_initialize: 'Callable[[Session], None]',
                       on_post_initialize: 'Callable[[Session], None]',
                       on_post_exit: 'Callable[[str], None]',
                       on_stderr_log: 'Optional[Callable[[str], None]]') -> 'Optional[Session]':
    return create_session(
        config=TEST_CONFIG,
        workspace_folders=workspace_folders,
        env=dict(),
        settings=MockSettings(),
        bootstrap_client=MockClient(),
        on_pre_initialize=on_pre_initialize,
        on_post_initialize=on_post_initialize,
        on_post_exit=on_post_exit,
        on_stderr_log=on_stderr_log)


class WindowRegistryTests(unittest.TestCase):

    def test_can_get_window_state(self):
        windows = WindowRegistry(TestGlobalConfigs(), TestDocumentHandlerFactory(),
                                 mock_start_session,
                                 test_sublime, MockHandlerDispatcher())
        windows.set_settings_factory(MockSettings())
        test_window = MockWindow()
        wm = windows.lookup(test_window)
        self.assertIsNotNone(wm)

    def test_removes_window_state(self):
        test_window = MockWindow([[MockView(__file__)]])
        windows = WindowRegistry(TestGlobalConfigs(), TestDocumentHandlerFactory(),
                                 mock_start_session,
                                 test_sublime, MockHandlerDispatcher())
        windows.set_settings_factory(MockSettings())
        wm = windows.lookup(test_window)
        wm.start_active_views()

        self.assertIsNotNone(wm)

        # closing views triggers window unload detection
        test_window.close()
        wm.handle_view_closed(MockView(__file__))
        test_sublime._run_timeout()

        self.assertEqual(len(windows._windows), 0)


class WindowManagerTests(unittest.TestCase):

    def make(
        self,
        *args: 'Any',
        **kwargs: 'Any'
    ) -> 'Tuple[MockWindow, MockDocuments, MockHandlerDispatcher, WindowManager]':
        """The args and kwargs are the arguments for a MockWindow"""
        docs = MockDocuments()
        dispatcher = MockHandlerDispatcher()
        window = MockWindow(*args, **kwargs)
        workspace = ProjectFolders(window)
        wm = WindowManager(
            window=window,
            workspace=workspace,
            settings=MockSettings(),
            configs=MockConfigs(),
            documents=docs,
            diagnostics=DiagnosticsStorage(None),
            session_starter=mock_start_session,
            sublime=test_sublime,
            handler_dispatcher=dispatcher)
        wm.start_active_views()
        for sessions in wm._sessions.values():
            for session in sessions:
                with session.ready_lock:
                    pass
        return window, docs, dispatcher, wm

    def test_can_start_active_views(self):
        _, docs, _, wm = self.make([[MockView(__file__)]])
        # session must be started
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name, __file__))
        self.assertListEqual(docs._documents, [__file__])

    def test_can_open_supported_view(self):
        window, docs, _, wm = self.make([[]])
        self.assertIsNone(wm.get_session(TEST_CONFIG.name, __file__))
        self.assertListEqual(docs._documents, [])

        # session must be started
        view = MockView(__file__)

        # WindowManager will call window.active_view() at some point during wm.activate_view
        window._files_in_groups = [[view]]

        wm.activate_view(view)
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name, __file__))
        self.assertEqual(len(docs._sessions), 1)

    def test_can_restart_sessions(self):
        _, docs, _, wm = self.make([[MockView(__file__)]])

        # session must be started
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name, __file__))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        wm.restart_sessions()

        # session must be started
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name, __file__))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

    def test_ends_sessions_when_closed(self):
        test_window, docs, _, wm = self.make([[MockView(__file__)]])

        # session must be started
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name, __file__))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        # closing views triggers window unload detection
        test_window.close()
        wm.handle_view_closed(MockView(__file__))
        test_sublime._run_timeout()
        self.assertEqual(len(wm._sessions), 0)
        self.assertEqual(len(docs._sessions), 0)

    def test_ends_sessions_when_quick_switching(self):
        test_window, docs, _, wm = self.make([[MockView(__file__)]], folders=[os.path.dirname(__file__)])

        # session must be started
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name, __file__))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        # change project_path
        new_project_path = tempfile.gettempdir()
        file_path = os.path.join(new_project_path, "testfile.py")
        test_window.set_folders([new_project_path])
        another_view = MockView(file_path)
        another_view.settings().set("syntax", "Unsupported Syntax")
        test_window._files_in_groups[0][0] = another_view
        wm.activate_view(another_view)

        self.assertEqual(len(wm._sessions), 0)
        self.assertEqual(len(docs._sessions), 0)

        # don't forget to check or we'll keep restarting sessions!
        self.assertEqual(wm.get_project_path(file_path), new_project_path)

    def test_offers_restart_on_crash(self):
        _, docs, _, wm = self.make([[MockView(__file__)]])

        # session must be started
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name, __file__))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        wm._handle_server_crash(TEST_CONFIG)

        # session must be started
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name, __file__))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

    def test_invokes_language_handler(self):
        _, docs, dispatcher, wm = self.make([[MockView(__file__)]])

        # session must be started
        self.assertIsNotNone(wm.get_session(TEST_CONFIG.name, __file__))

        # our starting document must be loaded
        self.assertListEqual(docs._documents, [__file__])

        # client_start_listeners, client_initialization_listeners,
        self.assertTrue(TEST_CONFIG.name in dispatcher._initialized)

    def test_returns_closest_workspace_folder(self):
        file_path = __file__
        top_folder = os.path.dirname(__file__)
        parent_folder = os.path.dirname(top_folder)
        _, _, _, wm = self.make([[MockView(__file__)]], [top_folder, parent_folder])
        self.assertEqual(top_folder, wm.get_project_path(file_path))

    def test_reuses_existing_session_for_foreign_file(self):
        top_folder = os.path.dirname(__file__)
        parent_folder = os.path.dirname(top_folder)
        _, _, _, wm = self.make([[MockView(__file__)]], [top_folder, parent_folder])
        with tempfile.TemporaryDirectory() as tmpdir:
            outside_file = os.path.join(tmpdir, "testfile.txt")
            with open(outside_file, "w") as fp:
                print("hello world", file=fp)
            another_view = MockView(outside_file)
            wm.activate_view(another_view)
            _ = wm.get_session(TEST_CONFIG.name, outside_file)
            self.assertEqual(len(wm._sessions), 1)
