import traceback

log_debug = False


def set_debug_logging(logging_enabled):
    global log_debug
    log_debug = logging_enabled


def debug(*args):
    """Print args to the console if the "debug" setting is True."""
    if log_debug:
        printf(*args)


def exception_log(message, ex):
    print(message)
    ex_traceback = ex.__traceback__
    print(''.join(traceback.format_exception(ex.__class__, ex, ex_traceback)))


def server_log(*args):
    printf(*args, prefix="server")


def printf(*args, prefix='LSP'):
    """Print args to the console, prefixed by the plugin name."""
    print(prefix + ":", *args)
