import unittest
from .diagnostics import DiagnosticsStorage
from .protocol import Diagnostic, Range, Point
from .test_protocol import LSP_MINIMAL_DIAGNOSTIC


test_file_path = "/test.py"
test_file_uri = "file:///test.py"
minimal_diagnostic = Diagnostic.from_lsp(LSP_MINIMAL_DIAGNOSTIC)

def make_update(diagnostics: 'List[dict]') -> dict:
    return {
        'uri': 'file:///test.py',
        'diagnostics': diagnostics
    }


class DiagnosticsStorageTest(unittest.TestCase):

    def test_empty_diagnostics(self):
        wd = DiagnosticsStorage(None)
        self.assertEqual(wd.get_by_file(__file__), {})
        self.assertEqual(wd.get(), {})

    def test_receive_diagnostics(self):
        ui = unittest.mock.Mock()
        wd = DiagnosticsStorage(ui)

        wd.receive("test_server", make_update([LSP_MINIMAL_DIAGNOSTIC]))
        view_diags = wd.get_by_file(test_file_path)
        self.assertEqual(len(view_diags["test_server"]), 1)
        self.assertEqual(view_diags["test_server"][0].message, LSP_MINIMAL_DIAGNOSTIC['message'])
        self.assertIn(test_file_path, wd.get())
        ui.update.assert_called_with(test_file_path, "test_server", {'/test.py': {'test_server': [minimal_diagnostic]}})

        wd.receive("test_server", make_update([]))
        view_diags = wd.get_by_file(test_file_path)
        self.assertEqual(len(view_diags), 0)
        self.assertEqual(wd.get(), {})
        ui.update.assert_called_with(test_file_path, "test_server", {})

    def test_remove_diagnostics(self):
        ui = unittest.mock.Mock()
        wd = DiagnosticsStorage(ui)

        wd.receive("test_server", make_update([LSP_MINIMAL_DIAGNOSTIC]))
        view_diags = wd.get_by_file(test_file_path)
        self.assertEqual(len(view_diags["test_server"]), 1)

        wd.remove(test_file_path, "test_server")

        view_diags = wd.get_by_file(test_file_path)
        self.assertEqual(len(view_diags), 0)
        self.assertEqual(wd.get(), {})
        ui.update.assert_called_with(test_file_path, "test_server", {})

    def test_clear_diagnostics(self):
        ui = unittest.mock.Mock()
        wd = DiagnosticsStorage(ui)

        wd.receive("test_server", make_update([LSP_MINIMAL_DIAGNOSTIC]))
        wd.clear()

        view_diags = wd.get_by_file(test_file_path)
        self.assertEqual(len(view_diags), 0)
        self.assertEqual(wd.get(), {})
        ui.update.assert_called_with(test_file_path, "test_server", {})

    def test_select(self):
        ui = unittest.mock.Mock()
        wd = DiagnosticsStorage(ui)

        wd.select_next()
        ui.select.assert_called_with(1)

        wd.select_previous()
        ui.select.assert_called_with(-1)

        wd.select_none()
        ui.deselect.assert_called()

