# TODO: narrow down imports
from .plugin.core.documents import *
from .plugin.core.main import shutdown
from .plugin.core.main import startup
from .plugin.core.panels import *
from .plugin.core.registry import LspRestartClientCommand

from .plugin.code_actions import *
from .plugin.color import *
from .plugin.completion import *
from .plugin.configuration import *
from .plugin.diagnostics import *
from .plugin.edit import *
from .plugin.execute_command import *
from .plugin.formatting import *
from .plugin.goto import *
from .plugin.highlights import *
from .plugin.hover import *
from .plugin.panels import *
from .plugin.references import *
from .plugin.rename import *
from .plugin.signature_help import *
from .plugin.symbols import *
from .plugin.workspace_symbol import *


plugin_loaded = startup
plugin_unloaded = shutdown
