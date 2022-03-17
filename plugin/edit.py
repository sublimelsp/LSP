from .core.edit import TextEditTuple
from .core.logging import debug
from .core.protocol import UINT_MAX
from .core.typing import List, Optional, Any, Generator, Iterable
from contextlib import contextmanager
import operator
import sublime
import sublime_plugin


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

    def run(self, edit: Any, changes: Optional[List[TextEditTuple]] = None) -> None:
        # Apply the changes in reverse, so that we don't invalidate the range
        # of any change that we haven't applied yet.
        if not changes:
            return
        with temporary_setting(self.view.settings(), "translate_tabs_to_spaces", False):
            view_version = self.view.change_count()
            last_row, _ = self.view.rowcol_utf16(self.view.size())
            for start, end, replacement, version in reversed(_sort_by_application_order(changes)):
                if version is not None and version != view_version:
                    debug('ignoring edit due to non-matching document version')
                    continue
                region = sublime.Region(
                    self.view.text_point_utf16(start[0], min(UINT_MAX, start[1]), clamp_column=True),
                    self.view.text_point_utf16(end[0], min(UINT_MAX, end[1]), clamp_column=True)
                )
                if start[0] > last_row and replacement[0] != '\n':
                    # Handle when a language server (eg gopls) inserts at a row beyond the document
                    # some editors create the line automatically, sublime needs to have the newline prepended.
                    self.apply_change(region, '\n' + replacement, edit)
                    last_row, _ = self.view.rowcol(self.view.size())
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


def _sort_by_application_order(changes: Iterable[TextEditTuple]) -> List[TextEditTuple]:
    # The spec reads:
    # > However, it is possible that multiple edits have the same start position: multiple
    # > inserts, or any number of inserts followed by a single remove or replace edit. If
    # > multiple inserts have the same position, the order in the array defines the order in
    # > which the inserted strings appear in the resulting text.
    # So we sort by start position. But if multiple text edits start at the same position,
    # we use the index in the array as the key.

    return list(sorted(changes, key=operator.itemgetter(0)))
