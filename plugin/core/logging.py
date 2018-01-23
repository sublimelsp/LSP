import traceback
from .settings import settings, PLUGIN_NAME


def debug(*args):
    """Print args to the console if the "debug" setting is True."""
    if settings.log_debug:
        printf(*args)


def exception_log(message, ex):
    print(message)
    ex_traceback = ex.__traceback__
    print(''.join(traceback.format_exception(ex.__class__, ex, ex_traceback)))


def server_log(*args):
    printf(*args, prefix="server")


def printf(*args, prefix=PLUGIN_NAME):
    """Print args to the console, prefixed by the plugin name."""
    print(prefix + ":", *args)
