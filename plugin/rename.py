from __future__ import annotations
from .core.edit import parse_range
from .core.edit import parse_workspace_edit
from .core.edit import WorkspaceChanges
from .core.protocol import PrepareRenameParams
from .core.protocol import PrepareRenameResult
from .core.protocol import Range
from .core.protocol import RenameParams
from .core.protocol import Request
from .core.protocol import WorkspaceEdit
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.registry import windows
from .core.sessions import Session
from .core.url import parse_uri
from .core.views import first_selection_region
from .core.views import get_line
from .core.views import range_to_region
from .core.views import text_document_position_params
from functools import partial
from typing import Any
from typing import cast
from typing_extensions import TypeGuard
import os
import sublime
import sublime_plugin


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

DISCARD_COMMAND_URL = sublime.command_url('chain', {
    'commands': [
        ['hide_panel', {}],
        ['lsp_hide_rename_buttons', {}]
    ]
})


def is_range_response(result: PrepareRenameResult) -> TypeGuard[Range]:
    return 'start' in result


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


# The flow of this command is fairly complicated so it deserves some documentation.
#
# When "LSP: Rename" is triggered from the Command Palette, the flow can go one of two ways:
#
# 1. Session doesn't have support for "prepareProvider":
#  - input() gets called with empty "args" - returns an instance of "RenameSymbolInputHandler"
#  - input overlay triggered
#  - user enters new name and confirms
#  - run() gets called with "new_name" argument
#  - rename is performed
#
# 2. Session has support for "prepareProvider":
#  - input() gets called with empty "args" - returns None
#  - run() gets called with no arguments
#  - "prepare" request is triggered on the session
#  - based on the "prepare" response, the "placeholder" value is computed
#  - "lsp_symbol_rename" command is re-triggered with computed "placeholder" argument
#  - run() gets called with "placeholder" argument set
#  - run() manually throws a TypeError
#  - input() gets called with "placeholder" argument set - returns an instance of "RenameSymbolInputHandler"
#  - input overlay triggered
#  - user enters new name and confirms
#  - run() gets called with "new_name" argument
#  - rename is performed
#
# Note how triggering the command programmatically triggers run() first while when triggering the command from
# the Command Palette the input() gets called first.

class LspSymbolRenameCommand(LspTextCommand):

    capability = 'renameProvider'

    def is_visible(
        self,
        new_name: str = "",
        placeholder: str = "",
        event: dict | None = None,
        point: int | None = None
    ) -> bool:
        if self.applies_to_context_menu(event):
            return self.is_enabled(event, point)
        return True

    def input(self, args: dict) -> sublime_plugin.TextInputHandler | None:
        if "new_name" in args:
            # Defer to "run" and trigger rename.
            return None
        prepare_provider_session = self.best_session("renameProvider.prepareProvider")
        if prepare_provider_session and "placeholder" not in args:
            # Defer to "run" and trigger "prepare" request.
            return None
        placeholder = args.get("placeholder", "")
        if not placeholder:
            point = args.get("point")
            # guess the symbol name
            if not isinstance(point, int):
                region = first_selection_region(self.view)
                if region is None:
                    return None
                point = region.b
            placeholder = self.view.substr(self.view.word(point))
        return RenameSymbolInputHandler(self.view, placeholder)

    def run(
        self,
        edit: sublime.Edit,
        new_name: str = "",
        placeholder: str = "",
        event: dict | None = None,
        point: int | None = None
    ) -> None:
        listener = self.get_listener()
        if listener:
            listener.purge_changes_async()
        location = get_position(self.view, event, point)
        prepare_provider_session = self.best_session("renameProvider.prepareProvider")
        if new_name or placeholder or not prepare_provider_session:
            if location is not None and new_name:
                self._do_rename(location, new_name)
                return
            # Trigger InputHandler manually.
            raise TypeError("required positional argument")
        if location is None:
            return
        params = cast(PrepareRenameParams, text_document_position_params(self.view, location))
        request = Request.prepareRename(params, self.view, progress=True)
        prepare_provider_session.send_request(
            request, partial(self._on_prepare_result, location), self._on_prepare_error)

    def _do_rename(self, position: int, new_name: str) -> None:
        session = self.best_session(self.capability)
        if not session:
            return
        position_params = text_document_position_params(self.view, position)
        params: RenameParams = {
            "textDocument": position_params["textDocument"],
            "position": position_params["position"],
            "newName": new_name,
        }
        request = Request.rename(params, self.view, progress=True)
        session.send_request(request, partial(self._on_rename_result_async, session))

    def _on_rename_result_async(self, session: Session, response: WorkspaceEdit | None) -> None:
        if not response:
            return session.window.status_message('Nothing to rename')
        changes = parse_workspace_edit(response)
        file_count = len(changes.keys())
        if file_count == 1:
            session.apply_parsed_workspace_edits(changes, True)
            return
        total_changes = sum(map(len, changes.values()))
        message = f"Replace {total_changes} occurrences across {file_count} files?"
        choice = sublime.yes_no_cancel_dialog(message, "Replace", "Preview", title="Rename")
        if choice == sublime.DialogResult.YES:
            session.apply_parsed_workspace_edits(changes, True)
        elif choice == sublime.DialogResult.NO:
            self._render_rename_panel(response, changes, total_changes, file_count, session.config.name)

    def _on_prepare_result(self, pos: int, response: PrepareRenameResult | None) -> None:
        if response is None:
            sublime.error_message("The current selection cannot be renamed")
            return
        if is_range_response(response):
            r = range_to_region(response, self.view)
            placeholder = self.view.substr(r)
            pos = r.a
        elif "placeholder" in response:
            placeholder = response["placeholder"]  # type: ignore
            pos = range_to_region(response["range"], self.view).a  # type: ignore
        else:
            placeholder = self.view.substr(self.view.word(pos))
        args = {"placeholder": placeholder, "point": pos}
        self.view.run_command("lsp_symbol_rename", args)

    def _on_prepare_error(self, error: Any) -> None:
        sublime.error_message("Rename error: {}".format(error["message"]))

    def _get_relative_path(self, file_path: str) -> str:
        wm = windows.lookup(self.view.window())
        if not wm:
            return file_path
        base_dir = wm.get_project_path(file_path)
        return os.path.relpath(file_path, base_dir) if base_dir else file_path

    def _render_rename_panel(
        self,
        workspace_edit: WorkspaceEdit,
        changes_per_uri: WorkspaceChanges,
        total_changes: int,
        file_count: int,
        session_name: str
    ) -> None:
        wm = windows.lookup(self.view.window())
        if not wm:
            return
        pm = wm.panel_manager
        if not pm:
            return
        panel = pm.ensure_rename_panel()
        if not panel:
            return
        to_render: list[str] = []
        reference_document: list[str] = []
        header_lines = f"{total_changes} changes across {file_count} files.\n"
        to_render.append(header_lines)
        reference_document.append(header_lines)
        ROWCOL_PREFIX = " {:>4}:{:<4} {}"
        for uri, (changes, _) in changes_per_uri.items():
            scheme, file = parse_uri(uri)
            filename_line = '{}:'.format(self._get_relative_path(file) if scheme == 'file' else uri)
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
        characters = "\n".join(to_render)
        base_dir = wm.get_project_path(self.view.file_name() or "")
        panel.settings().set("result_base_dir", base_dir)
        panel.run_command("lsp_clear_panel")
        wm.window.run_command("show_panel", {"panel": "output.rename"})
        panel.run_command('append', {
            'characters': characters,
            'force': True,
            'scroll_to_end': False
        })
        panel.set_reference_document("\n".join(reference_document))
        selection = panel.sel()
        selection.add(sublime.Region(0, panel.size()))
        panel.run_command('toggle_inline_diff')
        selection.clear()
        BUTTONS_HTML = BUTTONS_TEMPLATE.format(
            apply=sublime.command_url('chain', {
                'commands': [
                    [
                        'lsp_apply_workspace_edit',
                        {'session_name': session_name, 'edit': workspace_edit, 'is_refactoring': True}
                    ],
                    [
                        'hide_panel',
                        {}
                    ],
                    [
                        'lsp_hide_rename_buttons',
                        {}
                    ]
                ]
            }),
            discard=DISCARD_COMMAND_URL
        )
        pm.update_rename_panel_buttons([
            sublime.Phantom(sublime.Region(len(to_render[0]) - 1), BUTTONS_HTML, sublime.PhantomLayout.BLOCK)
        ])


class RenameSymbolInputHandler(sublime_plugin.TextInputHandler):
    def want_event(self) -> bool:
        return False

    def __init__(self, view: sublime.View, placeholder: str) -> None:
        self.view = view
        self._placeholder = placeholder

    def name(self) -> str:
        return "new_name"

    def placeholder(self) -> str:
        return self._placeholder

    def initial_text(self) -> str:
        return self.placeholder()

    def validate(self, name: str) -> bool:
        return len(name) > 0


class LspHideRenameButtonsCommand(sublime_plugin.WindowCommand):

    def run(self) -> None:
        wm = windows.lookup(self.window)
        if not wm:
            return
        if wm.panel_manager:
            wm.panel_manager.update_rename_panel_buttons([])
