from LSP.plugin.core.panels import ensure_server_panel
from LSP.plugin.core.panels import SERVER_PANEL_MAX_LINES
from LSP.plugin.core.panels import log_server_message
from unittesting import DeferrableTestCase
import sublime


class LspServerPanelTests(DeferrableTestCase):

    def setUp(self):
        super().setUp()
        self.window = sublime.active_window()
        if self.window is None:
            self.skipTest("window is None!")
            return
        self.view = self.window.active_view()
        panel = ensure_server_panel(self.window)
        if panel is None:
            self.skipTest("panel is None!")
            return
        panel.run_command("lsp_clear_panel")
        self.panel = panel

    def assert_total_lines_equal(self, expected_total_lines):
        actual_total_lines = len(self.panel.split_by_newlines(sublime.Region(0, self.panel.size())))
        self.assertEqual(actual_total_lines, expected_total_lines)

    def update_panel(self, msg: str) -> None:
        log_server_message(self.window, "test", msg)

    def test_server_panel_circular_behavior(self):
        n = SERVER_PANEL_MAX_LINES
        for i in range(0, n + 1):
            self.update_panel(str(i))
        self.update_panel("overflow")
        self.update_panel("overflow")
        self.update_panel("one\ntwo\nthree")
        # The panel only updates when visible but we don't want to test that as
        # it would hide the unittesting panel.
        self.assert_total_lines_equal(1)
