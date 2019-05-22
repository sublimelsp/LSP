import unittest
from .diagnostics import WindowDiagnostics
from .protocol import Diagnostic, Range, Point
# from .configurations import WindowConfigManager, _merge_dicts, ConfigManager, is_supported_syntax
# from .test_session import test_config, test_language
from .test_protocol import LSP_MINIMAL_DIAGNOSTIC


class WindowDiagnosticsTest(unittest.TestCase):

    def test_empty_diagnostics(self):
        wd = WindowDiagnostics()
        self.assertEqual(wd.get_by_path(__file__), [])

        # todo: remove

    def test_updated_diagnostics(self):
        wd = WindowDiagnostics()

        test_file_path = "test.py"
        diag = Diagnostic('message', Range(Point(0, 0), Point(1, 1)), 1, None, dict())

        wd.update(test_file_path, "test_server", [diag])
        view_diags = wd.get_by_path(test_file_path)
        self.assertEqual(len(view_diags), 1)
        self.assertEqual(view_diags[0], diag)

        wd.update(test_file_path, "test_server", [])
        view_diags = wd.get_by_path(test_file_path)
        self.assertEqual(len(view_diags), 0)

    def test_handle_diagnostics_update(self):
        wd = WindowDiagnostics()

        test_file_path = "/test.py"
        update = {
            'uri': 'file:///test.py',
            'diagnostics': [LSP_MINIMAL_DIAGNOSTIC]
        }

        wd.handle_client_diagnostics("test_server", update)

        view_diags = wd.get_by_path(test_file_path)
        self.assertEqual(len(view_diags), 1)

    def test_remove_diagnostics(self):
        wd = WindowDiagnostics()

        test_file_path = "test.py"
        diag = Diagnostic('message', Range(Point(0, 0), Point(1, 1)), 1, None, dict())

        wd.update(test_file_path, "test_server", [diag])
        view_diags = wd.get_by_path(test_file_path)
        self.assertEqual(len(view_diags), 1)

        wd.remove(test_file_path, "test_server")

        view_diags = wd.get_by_path(test_file_path)
        self.assertEqual(len(view_diags), 0)
