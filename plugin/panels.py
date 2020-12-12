from .core.panels import diagnostics_panel, language_servers_panel
import sublime_plugin


class LspToggleServerPanelCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        language_servers_panel.toggle(self.window)


class LspShowDiagnosticsPanelCommand(sublime_plugin.WindowCommand):
    def run(self) -> None:
        diagnostics_panel.toggle(self.window)
