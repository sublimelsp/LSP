from .core.logging import printf
from .core.main import ensure_server_panel
from .diagnostics import ensure_diagnostics_panel
from .core.panels import PanelName
from sublime_plugin import WindowCommand


class LspTogglePanelCommand(WindowCommand):
    def run(self, panel_type: str) -> None:
        if panel_type == PanelName.Diagnostics:
            ensure_diagnostics_panel(self.window)
        elif panel_type == PanelName.LanguageServers:
            ensure_server_panel(self.window)
        else:
            return
        panel_name = "output.{}".format(panel_type)
        command = "{}_panel".format("hide" if self.window.active_panel() == panel_name else "show")
        self.window.run_command(command, {"panel": panel_name})


class LspShowDiagnosticsPanelCommand(WindowCommand):
    def run(self) -> None:
        printf("lsp_show_diagnostics_panel is deprecated, use lsp_toggle_panel instead (see the keybindings)")
        self.window.run_command("lsp_toggle_panel", {"panel_type": PanelName.Diagnostics})
