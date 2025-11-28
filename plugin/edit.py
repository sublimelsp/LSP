from __future__ import annotations
from ..protocol import TextEdit
from ..protocol import WorkspaceEdit
from .core.edit import parse_range
from .core.logging import debug
from .core.registry import LspWindowCommand
from contextlib import contextmanager
from typing import Any, Generator, Iterable, Tuple
import operator
import re
import sublime
import sublime_plugin


TextEditTuple = Tuple[Tuple[int, int], Tuple[int, int], str]


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


class LspApplyWorkspaceEditCommand(LspWindowCommand):

    def run(
        self, session_name: str, edit: WorkspaceEdit, label: str | None = None, is_refactoring: bool = False
    ) -> None:
        if session := self.session_by_name(session_name):
            sublime.set_timeout_async(
                lambda: session.apply_workspace_edit_async(edit, label=label, is_refactoring=is_refactoring))
        else:
            debug('Could not find session', session_name, 'required to apply WorkspaceEdit')


class LspApplyDocumentEditCommand(sublime_plugin.TextCommand):
    re_placeholder = re.compile(r'\$(0|\{0:([^}]*)\})')

    def description(self, **kwargs: dict[str, Any]) -> str | None:
        return kwargs.get('label')  # pyright: ignore[reportReturnType]

    def run(
        self,
        edit: sublime.Edit,
        changes: list[TextEdit],
        label: str | None = None,
        required_view_version: int | None = None,
        process_placeholders: bool = False,
    ) -> None:
        # Apply the changes in reverse, so that we don't invalidate the range
        # of any change that we haven't applied yet.
        if not changes:
            return
        view_version = self.view.change_count()
        if required_view_version is not None and required_view_version != view_version:
            print('LSP: ignoring edit due to non-matching document version')
            return
        edits = [_parse_text_edit(change) for change in changes or []]
        with temporary_setting(self.view.settings(), "translate_tabs_to_spaces", False):
            last_row, _ = self.view.rowcol_utf16(self.view.size())
            placeholder_region_count = 0
            for start, end, replacement in reversed(_sort_by_application_order(edits)):
                placeholder_region: tuple[tuple[int, int], tuple[int, int]] | None = None
                if process_placeholders and replacement:
                    if parsed := self.parse_snippet(replacement):
                        replacement, (placeholder_start, placeholder_length) = parsed
                        # There might be newlines before the placeholder. Find the actual line
                        # and the character offset of the placeholder.
                        prefix = replacement[0:placeholder_start]
                        last_newline_start = prefix.rfind('\n')
                        start_line = start[0] + prefix.count('\n')
                        if last_newline_start == -1:
                            start_column = start[1] + placeholder_start
                        else:
                            start_column = len(prefix) - last_newline_start - 1
                        end_column = start_column + placeholder_length
                        placeholder_region = ((start_line, start_column), (start_line, end_column))
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
                if placeholder_region is not None:
                    if placeholder_region_count == 0:
                        self.view.sel().clear()
                    placeholder_region_count += 1
                    self.view.sel().add(sublime.Region(
                        self.view.text_point_utf16(*placeholder_region[0], clamp_column=True),
                        self.view.text_point_utf16(*placeholder_region[1], clamp_column=True)
                    ))
            if placeholder_region_count == 1:
                self.view.show(self.view.sel())

    def apply_change(self, region: sublime.Region, replacement: str, edit: sublime.Edit) -> None:
        if region.empty():
            self.view.insert(edit, region.a, replacement)
        elif len(replacement) > 0:
            self.view.replace(edit, region, replacement)
        else:
            self.view.erase(edit, region)

    def parse_snippet(self, replacement: str) -> tuple[str, tuple[int, int]] | None:
        if match := re.search(self.re_placeholder, replacement):
            placeholder = match.group(2) or ''
            new_replacement = replacement.replace(match.group(0), placeholder)
            placeholder_start_and_length = (match.start(0), len(placeholder))
            return (new_replacement, placeholder_start_and_length)
        return None


def _parse_text_edit(text_edit: TextEdit) -> TextEditTuple:
    return (
        parse_range(text_edit['range']['start']),
        parse_range(text_edit['range']['end']),
        # Strip away carriage returns -- SublimeText takes care of that.
        text_edit.get('newText', '').replace("\r", "")
    )


def _sort_by_application_order(changes: Iterable[TextEditTuple]) -> list[TextEditTuple]:
    # The spec reads:
    # > However, it is possible that multiple edits have the same start position: multiple
    # > inserts, or any number of inserts followed by a single remove or replace edit. If
    # > multiple inserts have the same position, the order in the array defines the order in
    # > which the inserted strings appear in the resulting text.
    # So we sort by start position. But if multiple text edits start at the same position,
    # we use the index in the array as the key.

    return list(sorted(changes, key=operator.itemgetter(0)))
