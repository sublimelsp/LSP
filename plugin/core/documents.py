import sublime
import sublime_plugin

from collections import OrderedDict
from .logging import debug
from .protocol import Notification
from .settings import settings
from .url import filename_to_uri
from .sessions import Session
from .configurations import is_supported_syntax, is_supportable_syntax
from .events import global_events
from .views import offset_to_point
from .windows import ViewLike, WindowLike

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
    assert ViewLike and WindowLike
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
            global_events.publish("view.on_load_async", self.view)

    def on_activated_async(self):
        if self.view.file_name() and not is_transient_view(self.view):
            global_events.publish("view.on_activated_async", self.view)

    def on_modified(self):
        if self.view.file_name():
            global_events.publish("view.on_modified", self.view)

    def on_post_save_async(self):
        global_events.publish("view.on_post_save_async", self.view)

    def on_close(self):
        if self.view.file_name() and self.view.is_primary():
            global_events.publish("view.on_close", self.view)


class DocumentHandlerFactory(object):

    def for_window(self, window: 'WindowLike'):
        return WindowDocumentHandler(window, global_events)


class WindowDocumentHandler(object):
    def __init__(self, window, events):
        self._window = window
        self._document_states = dict()  # type: Dict[str, DocumentState]
        self._pending_buffer_changes = dict()  # type: Dict[int, Dict]
        self._sessions = dict()  # type: Dict[str, Session]
        events.subscribe('view.on_load_async', self.handle_view_opened)
        events.subscribe('view.on_activated_async', self.handle_view_opened)
        events.subscribe('view.on_modified', self.handle_view_modified)
        events.subscribe('view.on_purge_changes', self.purge_changes)
        events.subscribe('view.on_post_save_async', self.handle_view_saved)
        events.subscribe('view.on_close', self.handle_view_closed)

    def add_session(self, session: Session):
        self._sessions[session.config.name] = session

    def remove_session(self, config_name: str):
        if config_name in self._sessions:
            del self._sessions[config_name]

    def reset(self):
        self._document_states.clear()

    def get_document_state(self, path: str) -> DocumentState:
        if path not in self._document_states:
            self._document_states[path] = DocumentState(path)
        return self._document_states[path]

    def has_document_state(self, path: str) -> bool:
        return path in self._document_states

    def handle_view_opened(self, view: sublime.View):
        file_name = view.file_name()
        if file_name and view.window() == self._window:
            if not self.has_document_state(file_name):
                ds = self.get_document_state(file_name)

                view.settings().set("show_definitions", False)
                if settings.show_view_status:
                    view.set_status("lsp_clients", ",".join(list(self._sessions)))

                for config_name, session in self._sessions.items():
                    params = {
                        "textDocument": {
                            "uri": filename_to_uri(file_name),
                            "languageId": session.config.languageId,
                            "text": view.substr(sublime.Region(0, view.size())),
                            "version": ds.version
                        }
                    }
                    session.client.send_notification(Notification.didOpen(params))

    def handle_view_closed(self, view: sublime.View):
        file_name = view.file_name()
        if view.window() == self._window:
            if file_name in self._document_states:
                del self._document_states[file_name]
                for config_name, session in self._sessions.items():
                    if session.client:
                        params = {"textDocument": {"uri": filename_to_uri(file_name)}}
                        session.client.send_notification(Notification.didClose(params))

    def handle_view_saved(self, view: sublime.View):
        file_name = view.file_name()
        if view.window() == self._window:
            if file_name in self._document_states:
                for config_name, session in self._sessions.items():
                    if session.client:
                        params = {"textDocument": {"uri": filename_to_uri(file_name)}}
                        session.client.send_notification(Notification.didSave(params))
            else:
                debug('document not tracked', file_name)

    def handle_view_modified(self, view: sublime.View):
        if view.window() == self._window:
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
        if file_name and view.window() == self._window:
            if view.buffer_id() in self._pending_buffer_changes:
                del self._pending_buffer_changes[view.buffer_id()]

                for config_name, session in self._sessions.items():
                    if session.client:
                        document_state = self.get_document_state(file_name)
                        uri = filename_to_uri(file_name)
                        params = {
                            "textDocument": {
                                "uri": uri,
                                "languageId": session.config.languageId,
                                "version": document_state.inc_version(),
                            },
                            "contentChanges": [{
                                "text": view.substr(sublime.Region(0, view.size()))
                            }]
                        }
                        session.client.send_notification(Notification.didChange(params))
