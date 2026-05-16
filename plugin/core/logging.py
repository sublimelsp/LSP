from __future__ import annotations

from .constants import ST_PACKAGES_PATH
from typing import Any
import inspect
import threading
import traceback

log_debug = False


def set_debug_logging(logging_enabled: bool) -> None:
    global log_debug
    log_debug = logging_enabled


def debug(*args: Any) -> None:
    """Print args to the console if the "debug" setting is True."""
    if log_debug:
        printf(*args)


def trace(print_callstack: bool = False, **values: Any) -> None:
    current_frame = inspect.currentframe()
    if current_frame is None:
        debug("TRACE (unknown frame)")
        return
    previous_frame = current_frame.f_back
    file_name, line_number, function_name, _, _ = inspect.getframeinfo(previous_frame)  # type: ignore
    file_name = file_name[len(ST_PACKAGES_PATH) + len("/LSP/"):]
    debug(f"TRACE {threading.current_thread().name:<16} {function_name:<32} {file_name}:{line_number}")
    if print_callstack:
        for frame in traceback.extract_stack():
            debug(f"TRACE {frame.filename}:{frame.lineno} in {frame.name}")
    for k, v in values.items():
        debug(f"TRACE {k}={v}")


def exception_log(message: str, ex: BaseException) -> None:
    print(message)
    ex_traceback = ex.__traceback__
    print(''.join(traceback.format_exception(ex.__class__, ex, ex_traceback)))


def exceptions_log(message: str, exs: list[Exception]) -> None:
    for ex in exs:
        exception_log(message, ex)


def printf(*args: Any, prefix: str = 'LSP') -> None:
    """Print args to the console, prefixed by the plugin name."""
    print(prefix + ":", *args)
