import traceback
from threading import Lock

MYPY = False
if MYPY:
    from typing import Any
    assert Any


log_debug = False
log_exceptions = True
log_server = True
mutex = Lock()


def set_debug_logging(logging_enabled: bool) -> None:
    global log_debug
    log_debug = logging_enabled


def set_exception_logging(logging_enabled: bool) -> None:
    global log_exceptions
    log_exceptions = logging_enabled


def set_server_logging(logging_enabled: bool) -> None:
    global log_server
    log_server = logging_enabled


def debug(*args: 'Any') -> None:
    """Print args to the console if the "debug" setting is True."""
    if log_debug:
        with mutex:
            printf(*args)


def exception_log(message: str, ex: Exception) -> None:
    if log_exceptions:
        with mutex:
            print(message)
            ex_traceback = ex.__traceback__
            print(''.join(traceback.format_exception(ex.__class__, ex, ex_traceback)))


def server_log(server_name: str, *args: 'Any') -> None:
    if log_server:
        with mutex:
            printf(*args, prefix=server_name)


def printf(*args: 'Any', prefix: str = 'LSP') -> None:
    """Print args to the console, prefixed by the plugin name."""
    print(prefix + ":", *args)
