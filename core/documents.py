import sublime

from collections import OrderedDict

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass

from .logging import debug
from .protocol import Notification, Point
from .settings import settings
from .url import filename_to_uri
from .configurations import config_for_scope
from .clients import client_for_view, window_clients
from .events import Events


def get_document_position(view: sublime.View, point) -> 'Optional[OrderedDict]':
    file_name = view.file_name()
    if file_name:
        if not point:
            point = view.sel()[0].begin()
        d = OrderedDict()  # type: OrderedDict[str, Any]
        d['textDocument'] = {"uri": filename_to_uri(file_name)}
        d['position'] = Point.from_text_point(view, point).to_lsp()
        return d
    else:
        return None


# TODO: this should be per-window ?
document_states = {}  # type: Dict[str, DocumentState]


class DocumentState:
    """Stores version count for documents open in a language service"""
    def __init__(self, path: str) -> 'None':
        self.path = path
        self.version = 0

    def inc_version(self):
        self.version += 1
        return self.version


def get_document_state(path: str) -> DocumentState:
    if path not in document_states:
        document_states[path] = DocumentState(path)
    return document_states[path]


pending_buffer_changes = dict()  # type: Dict[int, Dict]


def queue_did_change(view: sublime.View):
    buffer_id = view.buffer_id()
    buffer_version = 1
    pending_buffer = None
    if buffer_id in pending_buffer_changes:
        pending_buffer = pending_buffer_changes[buffer_id]
        buffer_version = pending_buffer["version"] + 1
        pending_buffer["version"] = buffer_version
    else:
        pending_buffer_changes[buffer_id] = {
            "view": view,
            "version": buffer_version
        }

    sublime.set_timeout_async(
        lambda: purge_did_change(buffer_id, buffer_version), 500)


def purge_did_change(buffer_id: int, buffer_version=None):
    if buffer_id not in pending_buffer_changes:
        return

    pending_buffer = pending_buffer_changes.get(buffer_id)

    if pending_buffer:
        if buffer_version is None or buffer_version == pending_buffer["version"]:
            notify_did_change(pending_buffer["view"])


def notify_did_open(view: sublime.View):
    config = config_for_scope(view)
    client = client_for_view(view)
    if client and config:
        view.settings().set("show_definitions", False)
        view_file = view.file_name()
        if view_file:
            if view_file not in document_states:
                ds = get_document_state(view_file)
                if settings.show_view_status:
                    view.set_status("lsp_clients", config.name)
                params = {
                    "textDocument": {
                        "uri": filename_to_uri(view_file),
                        "languageId": config.languageId,
                        "text": view.substr(sublime.Region(0, view.size())),
                        "version": ds.version
                    }
                }
                client.send_notification(Notification.didOpen(params))


def notify_did_close(view: sublime.View):
    file_name = view.file_name()
    if file_name:
        if file_name in document_states:
            del document_states[file_name]
            config = config_for_scope(view)
            clients = window_clients(sublime.active_window())
            if config and config.name in clients:
                client = clients[config.name]
                params = {"textDocument": {"uri": filename_to_uri(file_name)}}
                client.send_notification(Notification.didClose(params))


def notify_did_save(view: sublime.View):
    file_name = view.file_name()
    if file_name:
        if file_name in document_states:
            client = client_for_view(view)
            if client:
                params = {"textDocument": {"uri": filename_to_uri(file_name)}}
                client.send_notification(Notification.didSave(params))
        else:
            debug('document not tracked', file_name)


def notify_did_change(view: sublime.View):
    file_name = view.file_name()
    if file_name:
        if view.buffer_id() in pending_buffer_changes:
            del pending_buffer_changes[view.buffer_id()]
        # config = config_for_scope(view)
        client = client_for_view(view)
        if client:
            document_state = get_document_state(file_name)
            uri = filename_to_uri(file_name)
            params = {
                "textDocument": {
                    "uri": uri,
                    # "languageId": config.languageId, clangd does not like this field, but no server uses it?
                    "version": document_state.inc_version(),
                },
                "contentChanges": [{
                    "text": view.substr(sublime.Region(0, view.size()))
                }]
            }
            client.send_notification(Notification.didChange(params))


document_sync_initialized = False


def initialize_document_sync(text_document_sync_kind):
    global document_sync_initialized
    if document_sync_initialized:
        return
    document_sync_initialized = True
    # TODO: hook up events per scope/client
    Events.subscribe('view.on_load_async', notify_did_open)
    Events.subscribe('view.on_activated_async', notify_did_open)
    Events.subscribe('view.on_modified', queue_did_change)
    Events.subscribe('view.on_post_save_async', notify_did_save)
    Events.subscribe('view.on_close', notify_did_close)
