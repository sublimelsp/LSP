from .core.windows import ensure_server_panel
from .diagnostics import ensure_diagnostics_panel
from sublime import error_message
from sublime_plugin import WindowCommand

assert ensure_server_panel
assert ensure_diagnostics_panel


class LspTogglePanel(WindowCommand):
    def run(self, panel_type: str) -> None:
        if not isinstance(panel_type, str):
            return
        ensure_func = globals().get("ensure_{}_panel".format(panel_type), None)
        if not callable(ensure_func):
            error_message('There is no panel of type "{}"'.format(panel_type))
            return
        ensure_func(self.window)
        panel_name = "output.{}".format(panel_type)
        command = "{}_panel".format("hide" if self.window.active_panel() == panel_name else "show")
        self.window.run_command(command, {"panel": panel_name})
