import sublime
import sublime_plugin

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
from .configurations import config_for_scope, is_supported_view, is_supported_syntax, is_supportable_syntax
from .clients import client_for_view, client_for_closed_view, check_window_unloaded
from .events import Events

SUBLIME_WORD_MASK = 515


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


def get_position(view: sublime.View, event=None) -> int:
    if event:
        return view.window_to_text((event["x"], event["y"]))
    else:
        return view.sel()[0].begin()


def is_at_word(view: sublime.View, event) -> bool:
    pos = get_position(view, event)
    point_classification = view.classify(pos)
    if point_classification & SUBLIME_WORD_MASK:
        return True
    else:
        return False


# TODO: this should be per-window ?
document_states = {}  # type: Dict[int, Dict[str, DocumentState]]


class DocumentState:
    """Stores version count for documents open in a language service"""
    def __init__(self, path: str) -> 'None':
        self.path = path
        self.version = 0

    def inc_version(self):
        self.version += 1
        return self.version


def get_document_state(window: sublime.Window, path: str) -> DocumentState:
    window_document_states = document_states.setdefault(window.id(), {})
    if path not in window_document_states:
        window_document_states[path] = DocumentState(path)
    return window_document_states[path]


def has_document_state(window: sublime.Window, path: str):
    window_id = window.id()
    if window_id not in document_states:
        return False
    return path in document_states[window_id]


def clear_document_state(window: sublime.Window, path: str):
    window_id = window.id()
    if window_id in document_states:
        del document_states[window_id][path]


def clear_document_states(window: sublime.Window):
    if window.id() in document_states:
        del document_states[window.id()]


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
        window = view.window()
        view_file = view.file_name()
        if window and view_file:
            if not has_document_state(window, view_file):
                ds = get_document_state(window, view_file)
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
    window = sublime.active_window()
    if window and file_name:
        if has_document_state(window, file_name):
            clear_document_state(window, file_name)
            client = client_for_closed_view(view)
            if client:
                params = {"textDocument": {"uri": filename_to_uri(file_name)}}
                client.send_notification(Notification.didClose(params))


def notify_did_save(view: sublime.View):
    file_name = view.file_name()
    window = view.window()
    if window and file_name:
        if has_document_state(window, file_name):
            client = client_for_view(view)
            if client:
                params = {"textDocument": {"uri": filename_to_uri(file_name)}}
                client.send_notification(Notification.didSave(params))
        else:
            debug('document not tracked', file_name)


def notify_did_change(view: sublime.View):
    file_name = view.file_name()
    window = view.window()
    if window and file_name:
        if view.buffer_id() in pending_buffer_changes:
            del pending_buffer_changes[view.buffer_id()]
        # config = config_for_scope(view)
        client = client_for_view(view)
        if client:
            document_state = get_document_state(window, file_name)
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


class CloseListener(sublime_plugin.EventListener):
    def on_close(self, view):
        if is_supported_syntax(view.settings().get("syntax")):
            Events.publish("view.on_close", view)
        sublime.set_timeout_async(check_window_unloaded, 500)


class SaveListener(sublime_plugin.EventListener):
    def on_post_save_async(self, view):
        if is_supported_view(view):
            Events.publish("view.on_post_save_async", view)


def is_transient_view(view):
    window = view.window()
    return view == window.transient_view_in_group(window.active_group())


class DocumentSyncListener(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        self.view = view

    @classmethod
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        # This enables all of document sync for any supportable syntax
        # Global performance cost, consider a detect_lsp_support setting
        return syntax and (is_supported_syntax(syntax) or is_supportable_syntax(syntax))

    @classmethod
    def applies_to_primary_view_only(cls):
        return False

    def on_load_async(self):
        # skip transient views: if not is_transient_view(self.view):
        Events.publish("view.on_load_async", self.view)

    def on_modified(self):
        if self.view.file_name():
            Events.publish("view.on_modified", self.view)

    def on_activated_async(self):
        if self.view.file_name():
            Events.publish("view.on_activated_async", self.view)


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
