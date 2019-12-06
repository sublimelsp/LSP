from LSP.plugin.core.panels import SERVER_PANEL_MAX_LINES
from LSP.plugin.core.windows import ensure_server_panel
from setup import TextDocumentTestCase
import sublime


class LspServerPanelTests(TextDocumentTestCase):

    def setUp(self):
        super().setUp()
        window = self.view.window()
        if window is None:
            self.skipTest("window is None!")
            return
        panel = ensure_server_panel(window)
        if panel is None:
            self.skipTest("panel is None!")
            return
        panel.run_command("lsp_clear_panel")
        self.panel = panel

    def assert_total_lines_equal(self, expected_total_lines):
        actual_total_lines = len(self.panel.split_by_newlines(sublime.Region(0, self.panel.size())))
        self.assertEqual(actual_total_lines, expected_total_lines)

    def test_server_panel_circular_behavior(self):
        for i in range(0, SERVER_PANEL_MAX_LINES + 1):
            self.assert_total_lines_equal(max(1, i))
            self.panel.run_command("lsp_update_server_panel", {"prefix": "test", "message": str(i)})
        self.panel.run_command("lsp_update_server_panel", {"prefix": "test", "message": "overflow"})
        self.assert_total_lines_equal(SERVER_PANEL_MAX_LINES)
        self.panel.run_command("lsp_update_server_panel", {"prefix": "test", "message": "overflow"})
        self.assert_total_lines_equal(SERVER_PANEL_MAX_LINES)
        self.panel.run_command("lsp_update_server_panel", {"prefix": "test", "message": "one\ntwo\nthree"})
        self.assert_total_lines_equal(SERVER_PANEL_MAX_LINES)
        line_regions = self.panel.split_by_newlines(sublime.Region(0, self.panel.size()))
        self.assertEqual(self.panel.substr(line_regions[0]), "test: 6")
        self.assertEqual(len(line_regions), SERVER_PANEL_MAX_LINES)
        self.assertEqual(self.panel.substr(line_regions[SERVER_PANEL_MAX_LINES - 3]), "test: one")
        self.assertEqual(self.panel.substr(line_regions[SERVER_PANEL_MAX_LINES - 2]), "two")
        self.assertEqual(self.panel.substr(line_regions[SERVER_PANEL_MAX_LINES - 1]), "three")
