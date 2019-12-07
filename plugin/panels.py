from .core.main import ensure_server_panel
from .diagnostics import ensure_diagnostics_panel
from sublime_plugin import WindowCommand


class LspTogglePanelCommand(WindowCommand):
    def run(self, panel_type: str) -> None:
        if panel_type == "diagnostics":
            ensure_diagnostics_panel(self.window)
        elif panel_type == "server":
            ensure_server_panel(self.window)
        else:
            return
        panel_name = "output.{}".format(panel_type)
        command = "{}_panel".format("hide" if self.window.active_panel() == panel_name else "show")
        self.window.run_command(command, {"panel": panel_name})
