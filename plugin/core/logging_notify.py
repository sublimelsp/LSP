from __future__ import annotations
import sublime
from .settings import userprefs


def notify_error(window: sublime.Window | None, message: str, status_message: str | None = None) -> None:
    """Pick either of the 2 ways to show a user error notification message:
      - via a detailed console message and a short status message
      - via a blocking error modal dialog"""
    if not window:
        return
    if status_message is None:
        status_message = message
    if userprefs().suppress_error_dialogs:
        window.status_message(status_message)
        print("LSP: " + message)
    else:
        sublime.error_message(message)
