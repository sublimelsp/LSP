from .panels import ensure_panel
from .types import PANEL_FILE_REGEX
from .types import PANEL_LINE_REGEX
from .typing import Optional
import sublime


def ensure_diagnostics_panel(window: sublime.Window) -> Optional[sublime.View]:
    return ensure_panel(window, "diagnostics", PANEL_FILE_REGEX, PANEL_LINE_REGEX,
                        "Packages/LSP/Syntaxes/Diagnostics.sublime-syntax")
