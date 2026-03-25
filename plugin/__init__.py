from __future__ import annotations

from .api import AbstractPlugin
from .api import notification_handler
from .api import register_plugin
from .api import request_handler
from .api import unregister_plugin
from .core.collections import DottedDict
from .core.css import css
from .core.edit import apply_text_edits
from .core.file_watcher import FileWatcher
from .core.file_watcher import FileWatcherEvent
from .core.file_watcher import FileWatcherEventType
from .core.file_watcher import FileWatcherProtocol
from .core.file_watcher import register_file_watcher_implementation
from .core.promise import Promise
from .core.protocol import ClientNotification
from .core.protocol import ClientRequest
from .core.protocol import ClientResponse
from .core.protocol import Notification
from .core.protocol import Request
from .core.protocol import Response
from .core.protocol import ServerNotification
from .core.protocol import ServerRequest
from .core.protocol import ServerResponse
from .core.registry import LspTextCommand
from .core.registry import LspWindowCommand
from .core.sessions import Session
from .core.sessions import SessionBufferProtocol
from .core.sessions import SessionViewProtocol
from .core.types import ClientConfig
from .core.types import DebouncerNonThreadSafe
from .core.types import matches_pattern
from .core.url import filename_to_uri
from .core.url import parse_uri
from .core.url import uri_to_filename  # deprecated
from .core.version import __version__
from .core.views import MarkdownLangMap
from .core.views import uri_from_view
from .core.workspace import WorkspaceFolder

# This is the public API for LSP-* packages
__all__ = [
    'AbstractPlugin',
    'ClientConfig',
    'ClientNotification',
    'ClientRequest',
    'ClientResponse',
    'DebouncerNonThreadSafe',
    'DottedDict',
    'FileWatcher',
    'FileWatcherEvent',
    'FileWatcherEventType',
    'FileWatcherProtocol',
    'LspTextCommand',
    'LspWindowCommand',
    'MarkdownLangMap',
    'Notification',
    'Promise',
    'Request',
    'Response',
    'ServerNotification',
    'ServerRequest',
    'ServerResponse',
    'Session',
    'SessionBufferProtocol',
    'SessionViewProtocol',
    'WorkspaceFolder',
    '__version__',
    'apply_text_edits',
    'css',
    'filename_to_uri',
    'matches_pattern',
    'notification_handler',
    'parse_uri',
    'register_file_watcher_implementation',
    'register_plugin',
    'request_handler',
    'unregister_plugin',
    'uri_from_view',
    'uri_to_filename',  # deprecated
]
