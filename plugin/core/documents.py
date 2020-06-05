import sublime

from .logging import debug
from .registry import get_position
from .registry import LSPViewEventListener
from .typing import Optional, Iterable


SUBLIME_WORD_MASK = 515


def is_at_word(view: sublime.View, event: Optional[dict]) -> bool:
    pos = get_position(view, event)
    return position_is_word(view, pos)


def position_is_word(view: sublime.View, position: int) -> bool:
    point_classification = view.classify(position)
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
    @classmethod
    def is_applicable(cls, view_settings: dict) -> bool:
        return cls.has_supported_syntax(view_settings)

    @classmethod
    def applies_to_primary_view_only(cls) -> bool:
        return False

    def on_load_async(self) -> None:
        # skip transient views:
        if not is_transient_view(self.view):
            self.manager.activate_view(self.view)
            self.manager.documents.handle_did_open(self.view)

    def on_activated_async(self) -> None:
        if self.view.file_name() and not is_transient_view(self.view):
            self.manager.activate_view(self.view)
            self.manager.documents.handle_did_open(self.view)

    def on_text_changed(self, changes: Iterable[sublime.TextChange]) -> None:
        if self.view.file_name():
            last_change = list(changes)[-1]
            if last_change.a.pt == 0 and last_change.b.pt == 0 and last_change.str == '' and self.view.size() != 0:
                # Issue https://github.com/sublimehq/sublime_text/issues/3323
                # A special situation when changes externally. We receive two changes,
                # one that removes all content and one that has 0,0,'' parameters. We resend whole
                # file in that case to fix broken state.
                debug('Working around the on_text_changed bug {}'.format(self.view.file_name()))
                self.manager.documents.purge_changes(self.view)
                self.manager.documents.notify_sessions(self.view, None)
            else:
                self.manager.documents.handle_did_change(self.view, changes)

    def on_pre_save(self) -> None:
        if self.view.file_name():
            self.manager.documents.handle_will_save(self.view, reason=1)  # TextDocumentSaveReason.Manual

    def on_post_save_async(self) -> None:
        self.manager.documents.handle_did_save(self.view)

    def on_close(self) -> None:
        if self.view.file_name() and self.view.is_primary() and self.has_manager():
            self.manager.handle_view_closed(self.view)
            self.manager.documents.handle_did_close(self.view)
