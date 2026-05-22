from __future__ import annotations

from .api import AbstractPlugin
from .api import command_handler
from .api import IsApplicableContext
from .api import LspPlugin
from .api import notification_handler
from .api import OnPreStartContext
from .api import PluginStartError
from .api import register_plugin
from .api import request_handler
from .api import unregister_plugin
from .api import uri_handler
from .core.collections import DottedDict
from .core.constants import MarkdownLangMap
from .core.constants import ST_STORAGE_PATH
from .core.css import css
from .core.edit import apply_text_edits
from .core.file_watcher import FileWatcher
from .core.file_watcher import FileWatcherEvent
from .core.file_watcher import FileWatcherEventType
from .core.file_watcher import FileWatcherProtocol
from .core.file_watcher import register_file_watcher_implementation
from .core.promise import PackagedTask
from .core.promise import Promise
from .core.protocol import ClientNotification
from .core.protocol import ClientRequest
from .core.protocol import ClientResponse
from .core.protocol import Error
from .core.protocol import Notification
from .core.protocol import Request
from .core.protocol import Response
from .core.protocol import ServerNotification
from .core.protocol import ServerRequest
from .core.protocol import ServerResponse
from .core.protocol import TextPosition
from .core.registry import LspTextCommand
from .core.registry import LspWindowCommand
from .core.sessions import Session
from .core.sessions import SessionBufferProtocol
from .core.sessions import SessionViewProtocol
from .core.transports import TransportWrapper
from .core.types import ClientConfig
from .core.types import DebouncerNonThreadSafe
from .core.types import matches_pattern
from .core.url import filename_to_uri
from .core.url import parse_uri
from .core.url import uri_to_filename  # deprecated
from .core.version import __version__
from .core.views import first_selection_region
from .core.views import offset_to_text_position
from .core.views import point_to_offset
from .core.views import position_to_offset
from .core.views import region_to_range
from .core.views import text_document_identifier
from .core.views import text_document_position_params
from .core.views import uri_from_view
from .core.workspace import WorkspaceFolder
from .execute_command import LspExecuteCommand
from .locationpicker import LocationPicker

# This is the public API for LSP-* packages
__all__ = [
    'ST_STORAGE_PATH',
    'AbstractPlugin',
    'ClientConfig',
    'ClientNotification',
    'ClientRequest',
    'ClientResponse',
    'DebouncerNonThreadSafe',
    'DottedDict',
    'Error',
    'FileWatcher',
    'FileWatcherEvent',
    'FileWatcherEventType',
    'FileWatcherProtocol',
    'IsApplicableContext',
    'LocationPicker',
    'LspExecuteCommand',
    'LspPlugin',
    'LspTextCommand',
    'LspWindowCommand',
    'MarkdownLangMap',
    'Notification',
    'OnPreStartContext',
    'PackagedTask',
    'PluginStartError',
    'Promise',
    'Request',
    'Response',
    'ServerNotification',
    'ServerRequest',
    'ServerResponse',
    'Session',
    'SessionBufferProtocol',
    'SessionViewProtocol',
    'TextPosition',
    'TransportWrapper',
    'WorkspaceFolder',
    '__version__',
    'apply_text_edits',
    'command_handler',
    'css',
    'filename_to_uri',
    'first_selection_region',
    'matches_pattern',
    'notification_handler',
    'offset_to_text_position',
    'parse_uri',
    'point_to_offset',
    'position_to_offset',
    'region_to_range',
    'register_file_watcher_implementation',
    'register_plugin',
    'request_handler',
    'text_document_identifier',
    'text_document_position_params',
    'unregister_plugin',
    'uri_from_view',
    'uri_handler',
    'uri_to_filename',  # deprecated
]
