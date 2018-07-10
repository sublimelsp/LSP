from .windows import WindowManager, WindowRegistry, WindowLike
from .sessions import Session, create_session
from .test_session import TestClient, test_config
from .test_rpc import TestSettings
import os
import unittest


class TestView(object):
    def __init__(self, file_name):
        self._file_name = file_name

    def file_name(self):
        return self._file_name


class TestWindow(object):
    def id(self):
        return 0

    def folders(self):
        return [os.path.dirname(__file__)]

    def num_groups(self):
        return 1

    def active_group(self):
        return 0

    def active_view_in_group(self, group):
        return TestView(__file__)


class TestConfigs(object):
    def is_supported(self, view):
        return True

    def scope_config(self, view):
        return test_config


class TestDocuments(object):
    def __init__(self):
        self._documents = []

    def notify_did_open(self, view: TestView):
        self._documents.append(view.file_name())


def test_start_session(window, project_path, config, on_created: 'Callable'):
    return create_session(test_config, project_path, dict(), TestSettings(),
                          bootstrap_client=TestClient(),
                          on_created=on_created)


class WindowRegistryTests(unittest.TestCase):

    def test_can_get_window_state(self):
        windows = WindowRegistry(None, None, None, None)
        test_window = WindowLike()
        wm = windows.lookup(test_window)
        self.assertIsNotNone(wm)


class WindowManagerTests(unittest.TestCase):

    def test_has_no_sessions(self):
        wm = WindowManager(None, None, None, None, None)
        self.assertIsNone(wm.get_session('asdf'))

    def test_can_add_session(self):
        wm = WindowManager(None, None, None, None, None)
        self.assertIsNone(wm.get_session('asdf'))
        wm.add_session('asdf', Session(test_config, "", TestClient()))
        self.assertIsNotNone(wm.get_session('asdf'))

    def test_can_start_active_views(self):
        docs = TestDocuments()
        wm = WindowManager(TestWindow(), TestConfigs(), docs, None, test_start_session)
        wm.start_active_views()

        # session must be started (todo: verify session is ready)
        self.assertIsNotNone(wm.get_session(test_config.name))

        #
        self.assertListEqual(docs._documents, [__file__])

    # def test_can_(self):
    #     state = WindowState()
    #     state.request_session
