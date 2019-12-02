from .core.windows import ensure_server_panel
from .diagnostics import ensure_diagnostics_panel
from sublime import error_message
from sublime_lib import Panel
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
        Panel(self.window, "output.{}".format(panel_type)).toggle_visibility()
