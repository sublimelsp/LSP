from __future__ import annotations

from ..protocol import TextEdit, WorkspaceEdit
from .core.edit import parse_range, parse_workspace_edit, WorkspaceChanges
from .core.logging import debug
from .core.panels import PanelName
from .core.promise import Promise
from .core.registry import LspWindowCommand, windows
from .core.url import parse_uri
from .core.views import get_line
from .core.windows import WindowManager
from contextlib import contextmanager
from typing import Any, Callable, Generator, Iterable, Tuple, TYPE_CHECKING
import operator
import os
import re
import sublime
import sublime_plugin

if TYPE_CHECKING:
    from .core.sessions import Session

TextEditTuple = Tuple[Tuple[int, int], Tuple[int, int], str]

# Workspace edit panel resolvers keyed on Window ID.
g_workspace_edit_panel_resolvers: dict[int, Callable[[bool], None]] = {}

BUTTONS_TEMPLATE = """
<style>
    html {{
        background-color: transparent;
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
    }}
    a {{
        line-height: 1.6rem;
        padding-left: 0.6rem;
        padding-right: 0.6rem;
        border-width: 1px;
        border-style: solid;
        border-color: #fff4;
        border-radius: 4px;
        color: #cccccc;
        background-color: #3f3f3f;
        text-decoration: none;
    }}
    html.light a {{
        border-color: #000a;
        color: white;
        background-color: #636363;
    }}
    a.primary, html.light a.primary {{
        background-color: color(var(--accent) min-contrast(white 6.0));
    }}
</style>
<body id='lsp-buttons'>
    <a href='{apply}' class='primary'>Apply</a>&nbsp;
    <a href='{discard}'>Discard</a>
</body>"""


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


def prompt_for_workspace_edits(session: Session, response: WorkspaceEdit, label: str) -> Promise[bool]:
    changes = parse_workspace_edit(response, label)
    file_count = len(changes)
    if file_count <= 1:
        return Promise.resolve(True)
    total_changes = sum(len(value[0]) for value in changes.values())
    message = f"Apply {total_changes} changes across {file_count} files?"
    choice = sublime.yes_no_cancel_dialog(message, "Rename", "Preview", title=label)
    if choice == sublime.DialogResult.YES:
        return Promise.resolve(True)
    if choice == sublime.DialogResult.NO:
        promise, resolve = Promise[bool].packaged_task()
        _render_workspace_edit_panel(session, changes, label, total_changes, file_count, resolve)
        return promise
    return Promise.resolve(False)


def _render_workspace_edit_panel(
    session: Session,
    changes_per_uri: WorkspaceChanges,
    label: str,
    total_changes: int,
    file_count: int,
    on_done: Callable[[bool], None]
) -> None:
    def _get_relative_path(wm: WindowManager, file_path: str) -> str:
        base_dir = wm.get_project_path(file_path)
        return os.path.relpath(file_path, base_dir) if base_dir else file_path

    wm = windows.lookup(session.window)
    if not wm:
        on_done(False)
        return
    pm = wm.panel_manager
    if not pm:
        on_done(False)
        return
    panel = pm.ensure_workspace_edit_panel()
    if not panel:
        on_done(False)
        return
    to_render: list[str] = []
    reference_document: list[str] = []
    header_lines = f"{total_changes} changes across {file_count} files - {label}\n"
    to_render.append(header_lines)
    reference_document.append(header_lines)
    ROWCOL_PREFIX = " {:>4}:{:<4} {}"
    for uri, (changes, _, _) in changes_per_uri.items():
        scheme, file = parse_uri(uri)
        filename_line = '{}:'.format(_get_relative_path(wm, file) if scheme == 'file' else uri)
        to_render.append(filename_line)
        reference_document.append(filename_line)
        for edit in changes:
            start_row, start_col_utf16 = parse_range(edit['range']['start'])
            line_content = get_line(wm.window, file, start_row, strip=False) if scheme == 'file' else \
                '<no preview available>'
            start_col = utf16_to_code_points(line_content, start_col_utf16)
            original_line = ROWCOL_PREFIX.format(start_row + 1, start_col + 1, line_content.strip() + "\n")
            reference_document.append(original_line)
            if scheme == "file" and line_content:
                end_row, end_col_utf16 = parse_range(edit['range']['end'])
                new_text_rows = edit['newText'].split('\n')
                new_line_content = line_content[:start_col] + new_text_rows[0]
                if start_row == end_row and len(new_text_rows) == 1:
                    end_col = start_col if end_col_utf16 <= start_col_utf16 else \
                        utf16_to_code_points(line_content, end_col_utf16)
                    if end_col < len(line_content):
                        new_line_content += line_content[end_col:]
                to_render.append(
                    ROWCOL_PREFIX.format(start_row + 1, start_col + 1, new_line_content.strip() + "\n"))
            else:
                to_render.append(original_line)
    first_uri = next(iter(changes_per_uri))
    base_dir = wm.get_project_path(parse_uri(first_uri)[1]) if first_uri else None
    if base_dir:
        panel.settings().set("result_base_dir", base_dir)
    characters = "\n".join(to_render)
    panel.run_command("lsp_clear_panel")
    # Ensure window's potential unresolved panel is concluded.
    wm.window.run_command('lsp_conclude_workspace_edit_panel', {'window_id': wm.window.id(), 'accept': False})
    wm.window.run_command("show_panel", {"panel": f"output.{PanelName.WorkspaceEdit}"})
    panel.run_command('append', {
        'characters': characters,
        'force': True,
        'scroll_to_end': False
    })
    panel.set_reference_document("\n".join(reference_document))
    selection = panel.sel()
    selection.add(sublime.Region(0, panel.size()))
    is_inline_diff_active = panel.settings().get('workspace_edit.is_inline_diff_active')
    if not is_inline_diff_active:
        panel.run_command('toggle_inline_diff')
        panel.settings().set('workspace_edit.is_inline_diff_active', True)
    selection.clear()
    g_workspace_edit_panel_resolvers[wm.window.id()] = on_done
    buttons_html = BUTTONS_TEMPLATE.format(
        apply=sublime.command_url('chain', {
            'commands': [
                ['hide_panel', {}],
                ['lsp_conclude_workspace_edit_panel', {
                    'window_id': wm.window.id(),
                    'accept': True
                }]
            ]
        }),
        discard=sublime.command_url('chain', {
            'commands': [
                ['hide_panel', {}],
                ['lsp_conclude_workspace_edit_panel', {
                    'window_id': wm.window.id(),
                    'accept': False
                }]
            ]
        })
    )
    pm.update_workspace_edit_panel_buttons([
        sublime.Phantom(sublime.Region(len(to_render[0]) - 1), buttons_html, sublime.PhantomLayout.BLOCK)
    ])


def utf16_to_code_points(s: str, col: int) -> int:
    """Convert a position from UTF-16 code units to Unicode code points, usable for string slicing."""
    utf16_len = 0
    idx = 0
    for idx, c in enumerate(s):
        if utf16_len >= col:
            if utf16_len > col:  # If col is in the middle of a character (emoji), don't advance to the next code point
                idx -= 1
            break
        utf16_len += 1 if ord(c) < 65536 else 2
    else:
        idx += 1  # get_line function trims the trailing '\n'
    return idx


class LspConcludeWorkspaceEditPanelCommand(sublime_plugin.WindowCommand):

    def run(self, window_id: int, accept: bool) -> None:
        resolver = g_workspace_edit_panel_resolvers.pop(window_id, None)
        if resolver:
            resolver(accept)
        if (wm := windows.lookup(self.window)) and wm.panel_manager:
            wm.panel_manager.update_workspace_edit_panel_buttons([])
