from .plugin.core.main import startup, shutdown, LspStartClientCommand, LspRestartClientCommand

# TODO: narrow down imports
from .plugin.core.panels import *
from .plugin.core.documents import *
from .plugin.core.edit import *
from .plugin.completion import *
from .plugin.diagnostics import *
from .plugin.configuration import *
from .plugin.formatting import *
from .plugin.definition import *
from .plugin.hover import *
from .plugin.references import *
from .plugin.signature_help import *
from .plugin.code_actions import *
from .plugin.symbols import *
from .plugin.rename import *


def plugin_loaded():
    startup()


def plugin_unloaded():
    shutdown()
