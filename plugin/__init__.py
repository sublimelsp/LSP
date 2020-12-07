from .core.collections import DottedDict
from .core.css import css
from .core.protocol import Notification
from .core.protocol import Request
from .core.protocol import Response
from .core.sessions import AbstractPlugin
from .core.sessions import register_plugin
from .core.sessions import Session
from .core.sessions import SessionBufferProtocol
from .core.sessions import unregister_plugin
from .core.types import ClientConfig
from .core.types import WorkspaceFolder
from .core.url import filename_to_uri
from .core.url import uri_to_filename
from .core.version import __version__

# This is the public API for LSP-* packages
__all__ = [
    '__version__',
    'AbstractPlugin',
    'ClientConfig',
    'css',
    'DottedDict',
    'filename_to_uri',  # DEPRECATED: Use ClientConfig.map_client_path_to_server_uri instead
    'Notification',
    'register_plugin',
    'Request',
    'Response',
    'Session',
    'SessionBufferProtocol',
    'unregister_plugin',
    'uri_to_filename',  # DEPRECATED: Use ClientConfig.map_server_uri_to_client_path instead
    'WorkspaceFolder',
]
