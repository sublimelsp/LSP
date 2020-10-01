import sublime
import sublime_plugin
from .core.edit import sort_by_application_order, TextEdit
from .core.logging import debug
from .core.typing import List, Optional, Any, Generator
from contextlib import contextmanager


@contextmanager
def temporary_setting(settings: sublime.Settings, key: str, val: Any) -> Generator[None, None, None]:
    prev_val = None
    has_prev_val = settings.has(key)
    if has_prev_val:
        prev_val = settings.get(key)
    settings.set(key, val)
    yield
    settings.erase(key)
    if has_prev_val and settings.get(key) != prev_val:
        settings.set(key, prev_val)


class LspApplyDocumentEditCommand(sublime_plugin.TextCommand):

    def run(self, edit: Any, changes: Optional[List[TextEdit]] = None) -> None:
        # Apply the changes in reverse, so that we don't invalidate the range
        # of any change that we haven't applied yet.
        if not changes:
            return
        with temporary_setting(self.view.settings(), "translate_tabs_to_spaces", False):
            view_version = self.view.change_count()
            last_row, last_col = self.view.rowcol_utf16(self.view.size())
            for start, end, replacement, version in reversed(sort_by_application_order(changes)):
                if version is not None and version != view_version:
                    debug('ignoring edit due to non-matching document version')
                    continue
                region = sublime.Region(self.view.text_point_utf16(*start), self.view.text_point_utf16(*end))
                if start[0] > last_row and replacement[0] != '\n':
                    # Handle when a language server (eg gopls) inserts at a row beyond the document
                    # some editors create the line automatically, sublime needs to have the newline prepended.
                    self.apply_change(region, '\n' + replacement, edit)
                    last_row, last_col = self.view.rowcol(self.view.size())
                else:
                    self.apply_change(region, replacement, edit)

    def apply_change(self, region: sublime.Region, replacement: str, edit: Any) -> None:
        if region.empty():
            self.view.insert(edit, region.a, replacement)
        else:
            if len(replacement) > 0:
                self.view.replace(edit, region, replacement)
            else:
                self.view.erase(edit, region)
