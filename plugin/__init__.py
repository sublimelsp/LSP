from .api import notification_handler, request_handler
from .core.collections import DottedDict
from .core.css import css
from .core.edit import apply_text_edits
from .core.file_watcher import (
    FileWatcher,
    FileWatcherEvent,
    FileWatcherEventType,
    FileWatcherProtocol,
    register_file_watcher_implementation,
)
from .core.promise import Promise
from .core.protocol import Notification, Request, Response
from .core.registry import LspTextCommand, LspWindowCommand
from .core.sessions import (
    AbstractPlugin,
    register_plugin,
    Session,
    SessionBufferProtocol,
    SessionViewProtocol,
    unregister_plugin,
)
from .core.types import ClientConfig, DebouncerNonThreadSafe, matches_pattern
from .core.url import (
    filename_to_uri,
    parse_uri,
    uri_to_filename,  # deprecated
)
from .core.version import __version__
from .core.views import MarkdownLangMap, uri_from_view
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
    'notification_handler',
    'parse_uri',
    'Promise',
    'register_file_watcher_implementation',
    'register_plugin',
    'Request',
    'request_handler',
    'Response',
    'Session',
    'SessionBufferProtocol',
    'SessionViewProtocol',
    'unregister_plugin',
    'uri_from_view',
    'uri_to_filename',  # deprecated
    'WorkspaceFolder',
]
