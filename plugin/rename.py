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
from .core.typing import Any, Optional, Dict, List, TypeGuard
from .core.typing import cast
from .core.url import parse_uri
from .core.views import first_selection_region
from .core.views import get_line
from .core.views import range_to_region
from .core.views import text_document_position_params
from functools import partial
import os
import sublime
import sublime_plugin


def is_range_response(result: PrepareRenameResult) -> TypeGuard[Range]:
    return 'start' in result


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
        position: Optional[int] = None,
        event: Optional[dict] = None,
        point: Optional[int] = None
    ) -> bool:
        if self.applies_to_context_menu(event):
            return self.is_enabled(event, point)
        return True

    def input(self, args: dict) -> Optional[sublime_plugin.TextInputHandler]:
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
        position: Optional[int] = None,
        event: Optional[dict] = None,
        point: Optional[int] = None
    ) -> None:
        listener = self.get_listener()
        if listener:
            listener.purge_changes_async()
        location = position if position is not None else get_position(self.view, event, point)
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
        params = {
            "textDocument": position_params["textDocument"],
            "position": position_params["position"],
            "newName": new_name,
        }  # type: RenameParams
        request = Request.rename(params, self.view, progress=True)
        session.send_request(request, partial(self._on_rename_result_async, session))

    def _on_rename_result_async(self, session: Session, response: Optional[WorkspaceEdit]) -> None:
        if not response:
            return session.window.status_message('Nothing to rename')
        changes = parse_workspace_edit(response)
        count = len(changes.keys())
        if count == 1:
            session.apply_parsed_workspace_edits(changes)
            return
        total_changes = sum(map(len, changes.values()))
        message = "Replace {} occurrences across {} files?".format(total_changes, count)
        choice = sublime.yes_no_cancel_dialog(message, "Replace", "Dry Run")
        if choice == sublime.DIALOG_YES:
            session.apply_parsed_workspace_edits(changes)
        elif choice == sublime.DIALOG_NO:
            self._render_rename_panel(changes, total_changes, count)

    def _on_prepare_result(self, pos: int, response: Optional[PrepareRenameResult]) -> None:
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
        args = {"placeholder": placeholder, "position": pos}
        self.view.run_command("lsp_symbol_rename", args)

    def _on_prepare_error(self, error: Any) -> None:
        sublime.error_message("Rename error: {}".format(error["message"]))

    def _get_relative_path(self, file_path: str) -> str:
        wm = windows.lookup(self.view.window())
        if not wm:
            return file_path
        base_dir = wm.get_project_path(file_path)
        return os.path.relpath(file_path, base_dir) if base_dir else file_path

    def _render_rename_panel(self, changes_per_uri: WorkspaceChanges, total_changes: int, file_count: int) -> None:
        wm = windows.lookup(self.view.window())
        if not wm:
            return
        panel = wm.panel_manager and wm.panel_manager.ensure_rename_panel()
        if not panel:
            return
        to_render = []  # type: List[str]
        for uri, (changes, _) in changes_per_uri.items():
            scheme, file = parse_uri(uri)
            if scheme == "file":
                to_render.append('{}:'.format(self._get_relative_path(file)))
            else:
                to_render.append('{}:'.format(uri))
            for edit in changes:
                start = parse_range(edit['range']['start'])
                if scheme == "file":
                    line_content = get_line(wm.window, file, start[0])
                else:
                    line_content = '<no preview available>'
                to_render.append(" {:>4}:{:<4} {}".format(start[0] + 1, start[1] + 1, line_content))
            to_render.append("")  # this adds a spacing between filenames
        characters = "\n".join(to_render)
        base_dir = wm.get_project_path(self.view.file_name() or "")
        panel.settings().set("result_base_dir", base_dir)
        panel.run_command("lsp_clear_panel")
        wm.window.run_command("show_panel", {"panel": "output.rename"})
        fmt = "{} changes across {} files.\n\n{}"
        panel.run_command('append', {
            'characters': fmt.format(total_changes, file_count, characters),
            'force': True,
            'scroll_to_end': False
        })


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
