import sublime
from .typing import Optional


class CSS:
    def __init__(self) -> None:
        self.popups = sublime.load_resource("Packages/LSP/popups.css")
        self.popups_classname = "lsp_popup"
        self.notification = sublime.load_resource("Packages/LSP/notification.css")
        self.notification_classname = "notification"
        self.phantoms = sublime.load_resource("Packages/LSP/phantoms.css")
        self.sheets = sublime.load_resource("Packages/LSP/sheets.css")
        self.sheets_classname = "lsp_sheet"


_css = None  # type: Optional[CSS]


def load() -> None:
    global _css
    _css = CSS()


def css() -> CSS:
    global _css
    assert _css is not None
    return _css
