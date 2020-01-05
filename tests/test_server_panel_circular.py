from LSP.plugin.core.panels import SERVER_PANEL_MAX_LINES
from LSP.plugin.core.main import ensure_server_panel
from unittest import TestCase
import sublime


class LspServerPanelTests(TestCase):

    def setUp(self):
        super().setUp()
        window = sublime.active_window()
        if window is None:
            self.skipTest("window is None!")
            return
        self.view = window.active_view()
        panel = ensure_server_panel(window)
        if panel is None:
            self.skipTest("panel is None!")
            return
        panel.run_command("lsp_clear_panel")
        self.panel = panel

    def assert_total_lines_equal(self, expected_total_lines):
        actual_total_lines = len(self.panel.split_by_newlines(sublime.Region(0, self.panel.size())))
        self.assertEqual(actual_total_lines, expected_total_lines)

    def update_panel(self, msg: str) -> None:
        self.panel.run_command("lsp_update_server_panel", {"prefix": "test", "message": msg})

    def test_server_panel_circular_behavior(self):
        n = SERVER_PANEL_MAX_LINES
        for i in range(0, n + 1):
            self.assert_total_lines_equal(max(1, i))
            self.update_panel(str(i))
        self.update_panel("overflow")
        self.assert_total_lines_equal(n)
        self.update_panel("overflow")
        self.assert_total_lines_equal(n)
        self.update_panel("one\ntwo\nthree")
        self.assert_total_lines_equal(n)
        line_regions = self.panel.split_by_newlines(sublime.Region(0, self.panel.size()))
        self.assertEqual(self.panel.substr(line_regions[0]), "test: 6")
        self.assertEqual(len(line_regions), n)
        self.assertEqual(self.panel.substr(line_regions[n - 3]), "test: one")
        self.assertEqual(self.panel.substr(line_regions[n - 2]), "two")
        self.assertEqual(self.panel.substr(line_regions[n - 1]), "three")
