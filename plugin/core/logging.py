import traceback

log_debug = False
log_exceptions = True


def set_debug_logging(logging_enabled: bool) -> None:
    global log_debug
    log_debug = logging_enabled


def set_exception_logging(logging_enabled: bool) -> None:
    global log_exceptions
    log_exceptions = logging_enabled


def debug(*args):
    """Print args to the console if the "debug" setting is True."""
    if log_debug:
        printf(*args)


def exception_log(message: str, ex) -> None:
    if log_exceptions:
        print(message)
        ex_traceback = ex.__traceback__
        print(''.join(traceback.format_exception(ex.__class__, ex, ex_traceback)))


def server_log(server_name, *args) -> None:
    printf(*args, prefix=server_name)


def printf(*args, prefix='LSP'):
    """Print args to the console, prefixed by the plugin name."""
    print(prefix + ":", *args)
