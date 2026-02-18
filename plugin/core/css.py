from __future__ import annotations

import sublime


class CSS:
    def __init__(self) -> None:
        self.popups = sublime.load_resource("Packages/LSP/popups.css")
        self.popups_classname = "lsp_popup"
        self.notification = sublime.load_resource("Packages/LSP/notification.css")
        self.notification_classname = "notification"
        self.sheets = sublime.load_resource("Packages/LSP/sheets.css")
        self.sheets_classname = "lsp_sheet"
        self.inlay_hints = sublime.load_resource("Packages/LSP/inlay_hints.css")
        self.annotations = sublime.load_resource("Packages/LSP/annotations.css")
        self.annotations_classname = "lsp_annotation"


_css: CSS | None = None


def load() -> None:
    global _css
    _css = CSS()


def css() -> CSS:
    global _css
    assert _css is not None
    return _css
