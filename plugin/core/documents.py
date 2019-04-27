import sublime
import sublime_plugin

from .url import filename_to_uri
from .configurations import is_supported_syntax
from .events import global_events
from .views import offset_to_point
from .windows import ViewLike, WindowLike
from .settings import client_configs

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
    assert ViewLike and WindowLike
except ImportError:
    pass


SUBLIME_WORD_MASK = 515


def get_document_position(view: sublime.View, point: int) -> 'Optional[Dict[str, Any]]':
    file_name = view.file_name()
    if file_name:
        if not point:
            point = view.sel()[0].begin()
        d = dict()  # type: Dict[str, Any]
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


def is_transient_view(view: sublime.View) -> bool:
    window = view.window()
    if window:
        if window.get_view_index(view)[1] == -1:
            return True  # Quick panel transient views
        return view == window.transient_view_in_group(window.active_group())
    else:
        return True


class DocumentSyncListener(sublime_plugin.ViewEventListener):
    def __init__(self, view: 'sublime.View') -> None:
        self.view = view

    @classmethod
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        # This enables all of document sync for any supportable syntax
        # Global performance cost, consider a detect_lsp_support setting
        return syntax and is_supported_syntax(syntax, client_configs.all)

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
