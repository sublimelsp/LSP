from __future__ import annotations
from typing import Any, Optional
import traceback
import inspect
import sublime


log_debug = False


def set_debug_logging(logging_enabled: bool) -> None:
    global log_debug
    log_debug = logging_enabled


def debug(*args: Any) -> None:
    """Print args to the console if the "debug" setting is True."""
    if log_debug:
        printf(*args)


def trace() -> None:
    current_frame = inspect.currentframe()
    if current_frame is None:
        debug("TRACE (unknown frame)")
        return
    previous_frame = current_frame.f_back
    file_name, line_number, function_name, _, _ = inspect.getframeinfo(previous_frame)  # type: ignore
    file_name = file_name[len(sublime.packages_path()) + len("/LSP/"):]
    debug(f"TRACE {function_name:<32} {file_name}:{line_number}")


def exception_log(message: str, ex: Exception) -> None:
    print(message)
    ex_traceback = ex.__traceback__
    print(''.join(traceback.format_exception(ex.__class__, ex, ex_traceback)))


def printf(*args: Any, prefix: str = 'LSP') -> None:
    """Print args to the console, prefixed by the plugin name."""
    print(prefix + ":", *args)


def notify(window: sublime.Window | None, message: str, status_message: str = 'LSP: see console log…') -> None:
    """Pick either of the 2 ways to show a user notification message:
      - via a detailed console message and a short status message
      - via a blocking modal dialog"""
    from .settings import userprefs
    if not window:
        return
    if userprefs().suppress_error_dialogs:
        window.status_message(status_message)
        print(message)
    else:
        sublime.message_dialog(message)


def notify_error(window: sublime.Window | None, message: str, status_message: str = '❗LSP: see console log…') -> None:
    """Pick either of the 2 ways to show a user error notification message:
      - via a detailed console message and a short status message
      - via a blocking error modal dialog"""
    from .settings import userprefs
    if not window:
        return
    if userprefs().suppress_error_dialogs:
        window.status_message(status_message)
        print(message)
    else:
        sublime.error_message(message)
