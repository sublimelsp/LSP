import unittest
from .diagnostics import DiagnosticsStorage
from .protocol import Diagnostic, Range, Point
# from .configurations import WindowConfigManager, _merge_dicts, ConfigManager, is_supported_syntax
# from .test_session import test_config, test_language
from .test_protocol import LSP_MINIMAL_DIAGNOSTIC


class DiagnosticsStorageTest(unittest.TestCase):

    def test_empty_diagnostics(self):
        wd = DiagnosticsStorage(None)
        self.assertEqual(wd.get_by_file(__file__), {})

        # todo: remove

    def test_updated_diagnostics(self):
        wd = DiagnosticsStorage(None)

        test_file_path = "test.py"
        diag = Diagnostic('message', Range(Point(0, 0), Point(1, 1)), 1, None, dict())

        wd.update(test_file_path, "test_server", [diag])
        view_diags = wd.get_by_file(test_file_path)
        self.assertEqual(len(view_diags["test_server"]), 1)
        self.assertEqual(view_diags["test_server"][0], diag)

        wd.update(test_file_path, "test_server", [])
        view_diags = wd.get_by_file(test_file_path)
        self.assertEqual(len(view_diags), 0)

    def test_handle_diagnostics_update(self):
        wd = DiagnosticsStorage(None)

        test_file_path = "/test.py"
        update = {
            'uri': 'file:///test.py',
            'diagnostics': [LSP_MINIMAL_DIAGNOSTIC]
        }

        wd.receive("test_server", update)

        view_diags = wd.get_by_file(test_file_path)
        self.assertEqual(len(view_diags["test_server"]), 1)

    def test_remove_diagnostics(self):
        wd = DiagnosticsStorage(None)

        test_file_path = "test.py"
        diag = Diagnostic('message', Range(Point(0, 0), Point(1, 1)), 1, None, dict())

        wd.update(test_file_path, "test_server", [diag])
        view_diags = wd.get_by_file(test_file_path)
        self.assertEqual(len(view_diags["test_server"]), 1)

        wd.remove(test_file_path, "test_server")

        view_diags = wd.get_by_file(test_file_path)
        self.assertEqual(len(view_diags), 0)
