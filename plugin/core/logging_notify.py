from __future__ import annotations
import sublime
from .settings import userprefs

def notify_error(window: sublime.Window | None, message: str, status_message: str = 'LSP: see console log…',
                 severe: bool = True) -> None:
    """Pick either of the 2 ways to show a user error notification message:
      - via a detailed console message and a short status message
      - via a blocking error modal dialog (with severe=false non-error modal dialog)"""
    if not window:
        return
    if userprefs().suppress_error_dialogs:
        window.status_message(status_message)
        print(message)
    else:
        if severe:
            sublime.error_message(message)
        else:
            sublime.message_dialog(message)
