from .core.windows import ensure_server_panel
from .diagnostics import ensure_diagnostics_panel
from sublime_lib import Panel
from sublime_plugin import WindowCommand


class LspTogglePanelCommand(WindowCommand):
    def run(self, panel_type: str) -> None:
        if panel_type == "diagnostics":
            ensure_diagnostics_panel(self.window)
        elif panel_type == "server":
            ensure_server_panel(self.window)
        else:
            return
        Panel(self.window, "output.{}".format(panel_type)).toggle_visibility()
