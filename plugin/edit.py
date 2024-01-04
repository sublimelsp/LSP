from .core.edit import TextEditTuple
from .core.logging import debug
from .core.typing import List, Optional, Any, Generator, Iterable, Tuple
from contextlib import contextmanager
import operator
import re
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
    re_snippet = re.compile(r'\$(0|\{0:([^}]*)\})')

    def run(
        self, edit: sublime.Edit, changes: Optional[List[TextEditTuple]] = None, process_snippets: bool = False
    ) -> None:
        # Apply the changes in reverse, so that we don't invalidate the range
        # of any change that we haven't applied yet.
        if not changes:
            return
        with temporary_setting(self.view.settings(), "translate_tabs_to_spaces", False):
            view_version = self.view.change_count()
            last_row, _ = self.view.rowcol_utf16(self.view.size())
            snippet_region_count = 0
            for start, end, replacement, version in reversed(_sort_by_application_order(changes)):
                if version is not None and version != view_version:
                    debug('ignoring edit due to non-matching document version')
                    continue
                snippet_region = None  # type: Optional[Tuple[Tuple[int, int], Tuple[int, int]]]
                if process_snippets and replacement:
                    parsed = self.parse_snippet(replacement)
                    if parsed:
                        replacement, (placeholder_start, placeholder_length) = parsed
                        # There might be newlines before the placeholder. Find the actual line and character offset
                        # of the placeholder.
                        prefix = replacement[0:placeholder_start]
                        last_newline_start = prefix.rfind('\n')
                        start_line = start[0] + prefix.count('\n')
                        if last_newline_start == -1:
                            start_column = start[1] + placeholder_start
                        else:
                            start_column = len(prefix) - last_newline_start - 1
                        end_column = start_column + placeholder_length
                        snippet_region = ((start_line, start_column), (start_line, end_column))
                region = sublime.Region(
                    self.view.text_point_utf16(*start, clamp_column=True),
                    self.view.text_point_utf16(*end, clamp_column=True)
                )
                if start[0] > last_row and replacement[0] != '\n':
                    # Handle when a language server (eg gopls) inserts at a row beyond the document
                    # some editors create the line automatically, sublime needs to have the newline prepended.
                    self.apply_change(region, '\n' + replacement, edit)
                    last_row, _ = self.view.rowcol(self.view.size())
                else:
                    self.apply_change(region, replacement, edit)
                if snippet_region is not None:
                    if snippet_region_count == 0:
                        self.view.sel().clear()
                    snippet_region_count += 1
                    self.view.sel().add(sublime.Region(
                        self.view.text_point_utf16(*snippet_region[0], clamp_column=True),
                        self.view.text_point_utf16(*snippet_region[1], clamp_column=True)
                    ))
            if snippet_region_count == 1:
                self.view.show(self.view.sel())

    def apply_change(self, region: sublime.Region, replacement: str, edit: sublime.Edit) -> None:
        if region.empty():
            self.view.insert(edit, region.a, replacement)
        else:
            if len(replacement) > 0:
                self.view.replace(edit, region, replacement)
            else:
                self.view.erase(edit, region)

    def parse_snippet(self, replacement: str) -> Optional[Tuple[str, Tuple[int, int]]]:
        match = re.search(self.re_snippet, replacement)
        if not match:
            return
        placeholder = match.group(2) or ''
        new_replacement = replacement.replace(match.group(0), placeholder)
        placeholder_start_and_length = (match.start(0), len(placeholder))
        return (new_replacement, placeholder_start_and_length)


def _sort_by_application_order(changes: Iterable[TextEditTuple]) -> List[TextEditTuple]:
    # The spec reads:
    # > However, it is possible that multiple edits have the same start position: multiple
    # > inserts, or any number of inserts followed by a single remove or replace edit. If
    # > multiple inserts have the same position, the order in the array defines the order in
    # > which the inserted strings appear in the resulting text.
    # So we sort by start position. But if multiple text edits start at the same position,
    # we use the index in the array as the key.

    return list(sorted(changes, key=operator.itemgetter(0)))
