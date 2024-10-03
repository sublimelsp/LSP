from .core.collections import DottedDict
from .core.css import css
from .core.edit import apply_text_edits
from .core.file_watcher import FileWatcher
from .core.file_watcher import FileWatcherEvent
from .core.file_watcher import FileWatcherEventType
from .core.file_watcher import FileWatcherProtocol
from .core.file_watcher import register_file_watcher_implementation
from .core.protocol import Notification
from .core.protocol import Request
from .core.protocol import Response
from .core.registry import LspTextCommand
from .core.registry import LspWindowCommand
from .core.sessions import AbstractPlugin
from .core.sessions import register_plugin
from .core.sessions import Session
from .core.sessions import SessionBufferProtocol
from .core.sessions import unregister_plugin
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
    '__version__',
    'AbstractPlugin',
    'apply_text_edits',
    'ClientConfig',
    'css',
    'DebouncerNonThreadSafe',
    'DottedDict',
    'filename_to_uri',
    'FileWatcher',
    'FileWatcherEvent',
    'FileWatcherEventType',
    'FileWatcherProtocol',
    'LspTextCommand',
    'LspWindowCommand',
    'MarkdownLangMap',
    'matches_pattern',
    'Notification',
    'parse_uri',
    'register_file_watcher_implementation',
    'register_plugin',
    'Request',
    'Response',
    'Session',
    'SessionBufferProtocol',
    'unregister_plugin',
    'uri_from_view',
    'uri_to_filename',  # deprecated
    'WorkspaceFolder',
]
