from .core.diagnostics import ensure_diagnostics_panel
from .core.panels import ensure_log_panel
from .core.panels import is_panel_open
from .core.panels import PanelName
from sublime import Window
from sublime_plugin import WindowCommand


def toggle_output_panel(window: Window, panel_type: str) -> None:
    panel_name = "output.{}".format(panel_type)
    command = "{}_panel".format("hide" if is_panel_open(window, panel_type) else "show")
    window.run_command(command, {"panel": panel_name})


class LspToggleServerPanelCommand(WindowCommand):
    def run(self) -> None:
        ensure_log_panel(self.window)
        toggle_output_panel(self.window, PanelName.Log)


class LspShowDiagnosticsPanelCommand(WindowCommand):
    def run(self) -> None:
        ensure_diagnostics_panel(self.window)
        toggle_output_panel(self.window, PanelName.Diagnostics)
