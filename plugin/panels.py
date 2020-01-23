from .core.main import ensure_server_panel
from .diagnostics import ensure_diagnostics_panel
from .core.panels import PanelName
from sublime_plugin import WindowCommand
from sublime import Window


def toggle_output_panel(window: Window, panel_type: str) -> None:
    panel_name = "output.{}".format(panel_type)
    command = "{}_panel".format("hide" if window.active_panel() == panel_name else "show")
    window.run_command(command, {"panel": panel_name})


class LspToggleServerPanelCommand(WindowCommand):
    def run(self) -> None:
        ensure_server_panel(self.window)
        toggle_output_panel(self.window, PanelName.LanguageServers)


class LspShowDiagnosticsPanelCommand(WindowCommand):
    def run(self) -> None:
        ensure_diagnostics_panel(self.window)
        toggle_output_panel(self.window, PanelName.Diagnostics)
