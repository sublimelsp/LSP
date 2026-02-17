from __future__ import annotations

from LSP.plugin.core.panels import MAX_LOG_LINES_LIMIT_ON
from LSP.plugin.core.panels import PanelName
from LSP.plugin.core.registry import windows
from unittesting import DeferrableTestCase
import sublime


class LspServerPanelTests(DeferrableTestCase):

    def setUp(self):
        super().setUp()
        self.window = sublime.active_window()
        self.assertIsNotNone(self.window)
        self.wm = windows.lookup(self.window)
        self.assertIsNotNone(self.wm)
        if not self.wm:
            return
        self.view = self.window.active_view()
        self.panel = self.wm.panel_manager.get_panel(PanelName.Log)
        self.assertIsNotNone(self.panel)
        if not self.panel:
            return
        self.panel.run_command("lsp_clear_panel")

    def assert_total_lines_equal(self, expected_total_lines):
        actual_total_lines = len(self.panel.split_by_newlines(sublime.Region(0, self.panel.size())))
        self.assertEqual(actual_total_lines, expected_total_lines)

    def update_panel(self, msg: str) -> None:
        self.wm.log_server_message("test", msg)

    def test_server_panel_circular_behavior(self):
        n = MAX_LOG_LINES_LIMIT_ON
        for i in range(0, n + 1):
            self.update_panel(str(i))
        self.update_panel("overflow")
        self.update_panel("overflow")
        self.update_panel("one\ntwo\nthree")
        # The panel only updates when visible but we don't want to test that as
        # it would hide the unittesting panel.
        self.assert_total_lines_equal(1)
