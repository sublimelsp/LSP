from .plugin.core.main import startup, shutdown

# TODO: narrow down imports
from .plugin.core.panels import *
from .plugin.core.registry import LspRestartClientCommand
from .plugin.core.documents import *
from .plugin.panels import *
from .plugin.edit import *
from .plugin.completion import *
from .plugin.diagnostics import *
from .plugin.configuration import *
from .plugin.formatting import *
from .plugin.highlights import *
from .plugin.goto import *
from .plugin.hover import *
from .plugin.references import *
from .plugin.signature_help import *
from .plugin.code_actions import *
from .plugin.color import *
from .plugin.symbols import *
from .plugin.rename import *
from .plugin.execute_command import *
from .plugin.workspace_symbol import *

def plugin_loaded():
    startup()


def plugin_unloaded():
    shutdown()
