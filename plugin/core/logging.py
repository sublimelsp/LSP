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


def trace(depth: int = 1, **values: Any) -> None:
    """Set the depth to something large to print a stacktrace. Use the `values` kwargs to debug-print values."""
    current_frame = inspect.currentframe()
    if current_frame is None:
        debug("TRACE (unknown frame)")
        return
    output: list[str] = []
    while depth > 0:
        depth -= 1
        if current_frame := current_frame.f_back:
            file_name, line_number, function_name, _, _ = inspect.getframeinfo(current_frame)
            if file_name.startswith(ST_PACKAGES_PATH):
                file_name = file_name[len(ST_PACKAGES_PATH) + len("/LSP/") :]
            output.append(f'  {function_name:<32} {file_name}:{line_number}')
        else:
            break
    output.extend(f"    {k} = {v}" for k, v in values.items())
    print(f"TRACE (current thread: {threading.current_thread().name})\n" + '\n'.join(output))


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
