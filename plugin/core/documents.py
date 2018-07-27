import sublime
import sublime_plugin

from collections import OrderedDict
from .logging import debug
from .protocol import Notification
from .settings import settings
from .url import filename_to_uri
from .configurations import is_supported_syntax, is_supportable_syntax  # config_for_scope, is_supported_view,
# from .clients import client_for_view, client_for_closed_view, check_window_unloaded
from .events import Events
from .views import offset_to_point
from .windows import ViewLike

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
    assert ViewLike
except ImportError:
    pass


SUBLIME_WORD_MASK = 515


def get_document_position(view: sublime.View, point) -> 'Optional[OrderedDict]':
    file_name = view.file_name()
    if file_name:
        if not point:
            point = view.sel()[0].begin()
        d = OrderedDict()  # type: OrderedDict[str, Any]
        d['textDocument'] = {"uri": filename_to_uri(file_name)}
        d['position'] = offset_to_point(view, point).to_lsp()
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


class DocumentState:
    """Stores version count for documents open in a language service"""
    def __init__(self, path: str) -> 'None':
        self.path = path
        self.version = 0

    def inc_version(self):
        self.version += 1
        return self.version


class CloseListener(sublime_plugin.EventListener):
    def on_close(self, view):
        if is_supported_syntax(view.settings().get("syntax")):
            Events.publish("view.on_close", view)


class SaveListener(sublime_plugin.EventListener):
    def on_post_save_async(self, view):
        if is_supported_syntax(view.settings().get("syntax")):
            Events.publish("view.on_post_save_async", view)


def is_transient_view(view):
    window = view.window()
    if window:
        if window.get_view_index(view)[1] == -1:
            return True  # Quick panel transient views
        return view == window.transient_view_in_group(window.active_group())
    else:
        return True


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
        # skip transient views:
        if not is_transient_view(self.view):
            Events.publish("view.on_load_async", self.view)

    def on_modified(self):
        if self.view.file_name():
            Events.publish("view.on_modified", self.view)

    def on_activated_async(self):
        if self.view.file_name() and not is_transient_view(self.view):
            Events.publish("view.on_activated_async", self.view)


class DocumentHandlerFactory(object):

    def for_window(self):
        return SessionDocumentHandler()


class SessionDocumentHandler(object):
    def __init__(self):
        self._document_states = dict()  # type: Dict[str, DocumentState]
        self._pending_buffer_changes = dict()  # type: Dict[int, Dict]

    def initialize(self, events, session):
        self._session = session
        self._client = session.client
        events.subscribe('view.on_load_async', self.notify_did_open)
        events.subscribe('view.on_activated_async', self.notify_did_open)
        events.subscribe('view.on_modified', self.queue_did_change)
        events.subscribe('view.on_purge_changes', self.purge_changes)
        events.subscribe('view.on_post_save_async', self.notify_did_save)
        events.subscribe('view.on_close', self.notify_did_close)

    def reset(self, window: 'Any'):
        self._document_states.clear()

    def get_document_state(self, path: str) -> DocumentState:
        if path not in self._document_states:
            self._document_states[path] = DocumentState(path)
        return self._document_states[path]

    def has_document_state(self, path: str) -> bool:
        return path in self._document_states

    def notify_did_open(self, view: sublime.View):
        view.settings().set("show_definitions", False)
        window = view.window()
        view_file = view.file_name()
        if window and view_file:
            if not self.has_document_state(view_file):
                ds = self.get_document_state(view_file)
                if settings.show_view_status:
                    view.set_status("lsp_clients", self._session.config.name)
                params = {
                    "textDocument": {
                        "uri": filename_to_uri(view_file),
                        "languageId": self._session.config.languageId,
                        "text": view.substr(sublime.Region(0, view.size())),
                        "version": ds.version
                    }
                }
                self._client.send_notification(Notification.didOpen(params))

    def notify_did_close(self, view: sublime.View):
        file_name = view.file_name()
        window = sublime.active_window()
        if window and file_name:
            if file_name in self._document_states:
                del self._document_states[file_name]
                if self._client:
                    params = {"textDocument": {"uri": filename_to_uri(file_name)}}
                    self._client.send_notification(Notification.didClose(params))

    def notify_did_save(self, view: sublime.View):
        file_name = view.file_name()
        window = view.window()
        if window and file_name:
            if file_name in self._document_states:
                if self._client:
                    params = {"textDocument": {"uri": filename_to_uri(file_name)}}
                    self._client.send_notification(Notification.didSave(params))
            else:
                debug('document not tracked', file_name)

    def queue_did_change(self, view: sublime.View):
        buffer_id = view.buffer_id()
        buffer_version = 1
        pending_buffer = None
        if buffer_id in self._pending_buffer_changes:
            pending_buffer = self._pending_buffer_changes[buffer_id]
            buffer_version = pending_buffer["version"] + 1
            pending_buffer["version"] = buffer_version
        else:
            self._pending_buffer_changes[buffer_id] = {
                "view": view,
                "version": buffer_version
            }

        sublime.set_timeout_async(
            lambda: self.purge_did_change(buffer_id, buffer_version), 500)

    def purge_changes(self, view: sublime.View):
        self.purge_did_change(view.buffer_id())

    def purge_did_change(self, buffer_id: int, buffer_version=None):
        if buffer_id not in self._pending_buffer_changes:
            return

        pending_buffer = self._pending_buffer_changes.get(buffer_id)

        if pending_buffer:
            if buffer_version is None or buffer_version == pending_buffer["version"]:
                self.notify_did_change(pending_buffer["view"])

    def notify_did_change(self, view: sublime.View):
        file_name = view.file_name()
        window = view.window()
        if window and file_name:
            if view.buffer_id() in self._pending_buffer_changes:
                del self._pending_buffer_changes[view.buffer_id()]
            if self._client:
                document_state = self.get_document_state(file_name)
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
                self._client.send_notification(Notification.didChange(params))
