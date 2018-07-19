from .windows import WindowManager, WindowRegistry, WindowLike, ViewLike
from .sessions import create_session
from .test_session import TestClient, test_config
from .test_rpc import TestSettings
# from .logging import set_debug_logging, debug
import os
import unittest
try:
    from typing import Callable, List, Optional
    assert Callable and List and Optional
except ImportError:
    pass


class TestSublimeGlobal(object):
    DIALOG_CANCEL = 0
    DIALOG_YES = 1
    DIALOG_NO = 2

    def __init__(self):
        pass

    def message_dialog(self, msg: str) -> None:
        pass

    def ok_cancel_dialog(self, msg: str, ok_title: str) -> bool:
        return True

    def yes_no_cancel_dialog(self, msg, yes_title: str, no_title: str) -> int:
        return self.DIALOG_YES


class TestView(object):
    def __init__(self, file_name):
        self._file_name = file_name

    def file_name(self):
        return self._file_name


class TestWindow(object):
    def __init__(self, files_in_groups: 'List[List[ViewLike]]' = []) -> None:
        self._files_in_groups = files_in_groups

    def id(self):
        return 0

    def folders(self):
        return [os.path.dirname(__file__)]

    def num_groups(self):
        return len(self._files_in_groups)

    def active_group(self):
        return 0

    def project_data(self) -> Optional[dict]:
        return None

    def active_view(self) -> Optional[ViewLike]:
        return self.active_view_in_group(0)

    def active_view_in_group(self, group):
        if group < len(self._files_in_groups):
            files = self._files_in_groups[group]
            if len(files) > 0:
                return files[0]
            else:
                return TestView(None)

    def status_message(self, msg: str) -> None:
        pass


class TestConfigs(object):
    def is_supported(self, view):
        return view.file_name() is not None

    def scope_config(self, view):
        return test_config


class TestDocuments(object):
    def __init__(self):
        self._documents = []  # type: List[str]

    def initialize(self, text_document_sync_kind) -> None:
        pass

    def notify_did_open(self, view: ViewLike):
        file_name = view.file_name()
        if file_name:
            self._documents.append(file_name)

    def reset(self, window):
        self._documents = []


class TestDiagnostics(object):
    def __init__(self):
        pass

    def update(self, window: WindowLike, client_name: str, update: dict) -> None:
        pass

    def remove(self, view: ViewLike, client_name: str) -> None:
        pass


def test_start_session(window, project_path, config, on_created: 'Callable', on_ended: 'Callable'):
    return create_session(test_config, project_path, dict(), TestSettings(),
                          bootstrap_client=TestClient(),
                          on_created=on_created,
                          on_ended=on_ended)


class WindowRegistryTests(unittest.TestCase):

    def test_can_get_window_state(self):
        windows = WindowRegistry(TestConfigs(), TestDocuments(), TestDiagnostics(), test_start_session,
                                 TestSublimeGlobal())
        test_window = TestWindow()
        wm = windows.lookup(test_window)
        self.assertIsNotNone(wm)


class WindowManagerTests(unittest.TestCase):

    def test_can_start_active_views(self):
        docs = TestDocuments()
        wm = WindowManager(TestWindow([[TestView(__file__)]]), TestConfigs(), docs,
                           TestDiagnostics(), test_start_session, TestSublimeGlobal())
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))

        #
        self.assertListEqual(docs._documents, [__file__])

    def test_can_open_supported_view(self):
        docs = TestDocuments()
        window = TestWindow([[]])
        wm = WindowManager(window, TestConfigs(), docs, TestDiagnostics(), test_start_session, TestSublimeGlobal())

        wm.start_active_views()
        self.assertIsNone(wm.get_session(test_config.name))
        self.assertListEqual(docs._documents, [])

        # session must be started (todo: verify session is ready)
        wm.activate_view(TestView(__file__))
        self.assertIsNotNone(wm.get_session(test_config.name))
        self.assertListEqual(docs._documents, [__file__])

    def test_can_restart_sessions(self):
        docs = TestDocuments()
        wm = WindowManager(TestWindow([[TestView(__file__)]]), TestConfigs(), docs,
                           TestDiagnostics(), test_start_session, TestSublimeGlobal())
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

    def test_offers_restart_on_crash(self):
        docs = TestDocuments()
        wm = WindowManager(TestWindow([[TestView(__file__)]]), TestConfigs(), docs,
                           TestDiagnostics(), test_start_session, TestSublimeGlobal())
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
