import unittest
from collections import OrderedDict
from unittest import mock
from LSP.plugin.core.diagnostics import (
    DiagnosticsStorage, DiagnosticsWalker, DiagnosticsCursor, CURSOR_FORWARD, CURSOR_BACKWARD)
from LSP.plugin.core.protocol import Diagnostic, Point, Range, DiagnosticSeverity
from test_protocol import LSP_MINIMAL_DIAGNOSTIC
import sublime


TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import List, Dict
    assert List and Dict


test_file_path = "test.py" if sublime.platform() == "windows" else "/test.py"
test_file_uri = "file:///test.py"
second_file_path = "/test2.py"
second_file_uri = "file:///test2.py"
test_server_name = "test_server"
minimal_diagnostic = Diagnostic.from_lsp(LSP_MINIMAL_DIAGNOSTIC)


def at_row(row: int) -> Diagnostic:
    return Diagnostic('message', Range(Point(row, 0), Point(row, 1)), DiagnosticSeverity.Error, None, dict(), [])


def diagnostics(test_file_diags: 'List[Diagnostic]',
                second_file_diags: 'List[Diagnostic]' = []) -> 'Dict[str, Dict[str, List[Diagnostic]]]':
    diags = OrderedDict()  # type: Dict[str, Dict[str, List[Diagnostic]]]
    if test_file_diags:
        source_diags = {}
        source_diags[test_server_name] = test_file_diags
        diags[test_file_path] = source_diags
    if second_file_diags:
        source_diags = {}
        source_diags[test_server_name] = second_file_diags
        diags[second_file_path] = source_diags
    return diags


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
        ui.update.assert_called_with(
            test_file_path, "test_server", {test_file_path: {'test_server': [minimal_diagnostic]}})

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
        assert ui.deselect.call_count > 0


class DiagnosticsWalkerTests(unittest.TestCase):

    def test_empty(self):
        walk = mock.Mock()
        walker = DiagnosticsWalker([walk])
        walker.walk({})

        assert walk.begin.call_count == 1
        assert walk.begin_file.call_count == 0
        assert walk.diagnostic.call_count == 0
        assert walk.end.call_count == 1

    def test_one_diagnosic(self):

        walk = mock.Mock()
        walker = DiagnosticsWalker([walk])
        diags = {}  # type: Dict[str, Dict[str, List[Diagnostic]]]
        diags[test_file_path] = {}
        diags[test_file_path]["test_server"] = [minimal_diagnostic]
        walker.walk(diags)

        assert walk.begin.call_count == 1
        walk.begin_file.assert_called_with(test_file_path)
        walk.diagnostic.assert_called_with(minimal_diagnostic)
        assert walk.end.call_count == 1


row1 = at_row(1)
row5 = at_row(5)
row3 = at_row(3)
info = at_row(4)
info.severity = DiagnosticSeverity.Information
test_diagnostics = diagnostics([row1, info, row5], [row3])


class DiagnosticsCursorTest(unittest.TestCase):

    def test_empty(self) -> None:
        cursor = DiagnosticsCursor()

        walker = DiagnosticsWalker([cursor.from_position(CURSOR_FORWARD, test_file_path, Point(0, 0))])
        walker.walk({})
        self.assertIsNone(cursor.value)

    def test_from_no_position(self) -> None:
        cursor = DiagnosticsCursor()

        walker = DiagnosticsWalker([cursor.from_position(CURSOR_FORWARD)])
        walker.walk(test_diagnostics)
        self.assertEqual((test_file_path, row1), cursor.value)

    def test_from_no_position_backwards(self) -> None:
        cursor = DiagnosticsCursor()

        walker = DiagnosticsWalker([cursor.from_position(CURSOR_BACKWARD)])
        walker.walk(test_diagnostics)
        self.assertEqual((second_file_path, row3), cursor.value)

    def test_from_file_position(self) -> None:
        cursor = DiagnosticsCursor()

        walker = DiagnosticsWalker([cursor.from_position(CURSOR_FORWARD, test_file_path, Point(0, 0))])
        walker.walk(test_diagnostics)
        self.assertEqual((test_file_path, row1), cursor.value)

    def test_from_file_position_backward(self) -> None:
        cursor = DiagnosticsCursor()

        walker = DiagnosticsWalker([cursor.from_position(CURSOR_BACKWARD, test_file_path, Point(10, 0))])
        walker.walk(test_diagnostics)
        self.assertEqual((test_file_path, row5), cursor.value)

    def test_from_other_file_position_wrap(self) -> None:
        cursor = DiagnosticsCursor()

        walker = DiagnosticsWalker([cursor.from_position(CURSOR_FORWARD, second_file_path, Point(5, 0))])
        walker.walk(test_diagnostics)

        self.assertEqual((test_file_path, row1), cursor.value)

    def test_from_file_position_backward_wrap(self) -> None:
        cursor = DiagnosticsCursor()

        walker = DiagnosticsWalker([cursor.from_position(CURSOR_BACKWARD, test_file_path, Point(0, 0))])
        walker.walk(test_diagnostics)
        self.assertEqual((second_file_path, row3), cursor.value)

    def test_from_other_file_position_backwards(self) -> None:
        cursor = DiagnosticsCursor()

        walker = DiagnosticsWalker([cursor.from_position(CURSOR_BACKWARD, second_file_path, Point(1, 0))])
        walker.walk(test_diagnostics)
        self.assertEqual((test_file_path, row5), cursor.value)

    def test_updated_diagnostic_remains(self) -> None:

        cursor = DiagnosticsCursor()
        walker = DiagnosticsWalker([cursor.from_position(CURSOR_FORWARD)])

        walker.walk(test_diagnostics)
        self.assertEqual((test_file_path, row1), cursor.value)

        walker = DiagnosticsWalker([cursor.update()])
        walker.walk(test_diagnostics)

        self.assertEqual((test_file_path, row1), cursor.value)

    def test_updated_diagnostic_gone(self) -> None:
        cursor = DiagnosticsCursor()
        walker = DiagnosticsWalker([cursor.from_position(CURSOR_FORWARD)])

        walker.walk(test_diagnostics)
        self.assertEqual((test_file_path, row1), cursor.value)

        walker = DiagnosticsWalker([cursor.update()])
        walker.walk({})

        self.assertEqual(None, cursor.value)

    def test_from_diagnostic_to_same(self) -> None:
        cursor = DiagnosticsCursor()

        diags = diagnostics([row1])

        walker = DiagnosticsWalker([cursor.from_position(CURSOR_FORWARD)])
        walker.walk(diags)
        self.assertEqual((test_file_path, row1), cursor.value)

        walker = DiagnosticsWalker([cursor.from_diagnostic(CURSOR_FORWARD)])
        walker.walk(diags)
        self.assertEqual((test_file_path, row1), cursor.value)

        walker = DiagnosticsWalker([cursor.from_diagnostic(CURSOR_BACKWARD)])
        walker.walk(diags)
        self.assertEqual((test_file_path, row1), cursor.value)

    def test_from_diagnostic_forward(self) -> None:

        cursor = DiagnosticsCursor()

        walker = DiagnosticsWalker([cursor.from_position(CURSOR_FORWARD)])
        walker.walk(test_diagnostics)
        self.assertEqual((test_file_path, row1), cursor.value)

        walker = DiagnosticsWalker([cursor.from_diagnostic(CURSOR_FORWARD)])
        walker.walk(test_diagnostics)
        self.assertEqual((test_file_path, row5), cursor.value)

        walker = DiagnosticsWalker([cursor.from_diagnostic(CURSOR_FORWARD)])
        walker.walk(test_diagnostics)
        self.assertEqual((second_file_path, row3), cursor.value)

        walker = DiagnosticsWalker([cursor.from_diagnostic(CURSOR_FORWARD)])
        walker.walk(test_diagnostics)
        self.assertEqual((test_file_path, row1), cursor.value)

    def test_from_diagnostic_backward(self) -> None:

        cursor = DiagnosticsCursor()

        walker = DiagnosticsWalker([cursor.from_position(CURSOR_BACKWARD)])
        walker.walk(test_diagnostics)
        self.assertEqual((second_file_path, row3), cursor.value)

        walker = DiagnosticsWalker([cursor.from_diagnostic(CURSOR_BACKWARD)])
        walker.walk(test_diagnostics)
        self.assertEqual((test_file_path, row5), cursor.value)

        walker = DiagnosticsWalker([cursor.from_diagnostic(CURSOR_BACKWARD)])
        walker.walk(test_diagnostics)
        self.assertEqual((test_file_path, row1), cursor.value)

        walker = DiagnosticsWalker([cursor.from_diagnostic(CURSOR_BACKWARD)])
        walker.walk(test_diagnostics)
        self.assertEqual((second_file_path, row3), cursor.value)
