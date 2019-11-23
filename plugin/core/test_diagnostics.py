import unittest
from unittest import mock
from .diagnostics import DiagnosticsStorage, DiagnosticsWalker
from .protocol import Diagnostic
from .test_protocol import LSP_MINIMAL_DIAGNOSTIC

TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import List, Dict
    assert List and Dict


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
        ui = mock.Mock()
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
        ui = mock.Mock()
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
        ui = mock.Mock()
        wd = DiagnosticsStorage(ui)

        wd.receive("test_server", make_update([LSP_MINIMAL_DIAGNOSTIC]))
        wd.clear()

        view_diags = wd.get_by_file(test_file_path)
        self.assertEqual(len(view_diags), 0)
        self.assertEqual(wd.get(), {})
        ui.update.assert_called_with(test_file_path, "test_server", {})

    def test_select(self):
        ui = mock.Mock()
        wd = DiagnosticsStorage(ui)

        wd.select_next()
        ui.select.assert_called_with(1)

        wd.select_previous()
        ui.select.assert_called_with(-1)

        wd.select_none()
        ui.deselect.assert_called()


class DiagnosticsWalkerTests(unittest.TestCase):

    def test_empty(self):
        walk = mock.Mock()
        walker = DiagnosticsWalker([walk])
        walker.walk({})

        walk.begin.assert_called_once()
        walk.begin_file.assert_not_called()
        walk.diagnostic.assert_not_called()
        walk.end.assert_called_once()

    def test_one_diagnosic(self):

        walk = mock.Mock()
        walker = DiagnosticsWalker([walk])
        diags = {}  # type: Dict[str, Dict[str, List[Diagnostic]]]
        diags[test_file_path] = {}
        diags[test_file_path]["test_server"] = [minimal_diagnostic]
        walker.walk(diags)

        walk.begin.assert_called_once()
        walk.begin_file.assert_called_with(test_file_path)
        walk.diagnostic.assert_called_with(minimal_diagnostic)
        walk.end.assert_called_once()
