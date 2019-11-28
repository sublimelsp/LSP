import sublime

from .url import filename_to_uri
from .configurations import is_supported_syntax
from .views import offset_to_point
from .windows import ViewLike, WindowLike
from .settings import client_configs
from .registry import LSPViewEventListener

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


def get_position(view: sublime.View, event: 'Optional[dict]' = None) -> int:
    if event:
        return view.window_to_text((event["x"], event["y"]))
    else:
        return view.sel()[0].begin()


def is_at_word(view: sublime.View, event: 'Optional[dict]') -> bool:
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


class DocumentSyncListener(LSPViewEventListener):
    def __init__(self, view: 'sublime.View') -> None:
        super().__init__(view)

    @classmethod
    def is_applicable(cls, settings: dict) -> bool:
        syntax = settings.get('syntax')  # type: 'Optional[str]'
        # This enables all of document sync for any supportable syntax
        # Global performance cost, consider a detect_lsp_support setting
        if not syntax:
            return False
        else:
            return is_supported_syntax(syntax, client_configs.all)

    @classmethod
    def applies_to_primary_view_only(cls) -> bool:
        return False

    def on_load_async(self) -> None:
        # skip transient views:
        if not is_transient_view(self.view):
            self.manager.activate_view(self.view)
            self.manager.documents.handle_view_opened(self.view)

    def on_activated_async(self) -> None:
        if self.view.file_name() and not is_transient_view(self.view):
            self.manager.activate_view(self.view)
            self.manager.documents.handle_view_opened(self.view)

    def on_modified(self) -> None:
        if self.view.file_name():
            self.manager.documents.handle_view_modified(self.view)

    def on_post_save_async(self) -> None:
        self.manager.documents.handle_view_saved(self.view)

    def on_close(self) -> None:
        if self.view.file_name() and self.view.is_primary():
            self.manager.handle_view_closed(self.view)
            self.manager.documents.handle_view_closed(self.view)
