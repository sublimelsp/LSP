import traceback

MYPY = False
if MYPY:
    from typing import Any
    assert Any


log_debug = False
log_exceptions = True


def set_debug_logging(logging_enabled: bool) -> None:
    global log_debug
    log_debug = logging_enabled


def set_exception_logging(logging_enabled: bool) -> None:
    global log_exceptions
    log_exceptions = logging_enabled


def debug(*args: 'Any') -> None:
    """Print args to the console if the "debug" setting is True."""
    if log_debug:
        printf(*args)


def exception_log(message: str, ex: Exception) -> None:
    if log_exceptions:
        print(message)
        ex_traceback = ex.__traceback__
        print(''.join(traceback.format_exception(ex.__class__, ex, ex_traceback)))


def printf(*args: 'Any', prefix: str = 'LSP') -> None:
    """Print args to the console, prefixed by the plugin name."""
    print(prefix + ":", *args)
