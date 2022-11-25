from .core.edit import parse_workspace_edit
from .core.edit import TextEditTuple
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.registry import windows
from .core.sessions import Session
from .core.typing import Any, Optional, Dict, List
from .core.url import parse_uri
from .core.views import first_selection_region
from .core.views import get_line
from .core.views import range_to_region
from .core.views import text_document_position_params
import functools
import os
import sublime
import sublime_plugin


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


class LspSymbolRenameCommand(LspTextCommand):

    capability = 'renameProvider'

    # mypy: Signature of "is_enabled" incompatible with supertype "LspTextCommand"
    def is_enabled(  # type: ignore
        self,
        new_name: str = "",
        placeholder: str = "",
        position: Optional[int] = None,
        event: Optional[dict] = None,
        point: Optional[int] = None
    ) -> bool:
        if self.best_session("renameProvider.prepareProvider"):
            # The language server will tell us if the selection is on a valid token.
            return True
        return super().is_enabled(event, point)

    def is_visible(
        self,
        new_name: str = "",
        placeholder: str = "",
        position: Optional[int] = None,
        event: Optional[dict] = None,
        point: Optional[int] = None
    ) -> bool:
        if event is not None and 'x' in event:
            return self.is_enabled(new_name, placeholder, position, event, point)
        return True

    def input(self, args: dict) -> Optional[sublime_plugin.TextInputHandler]:
        if "new_name" not in args:
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
        else:
            return None

    def run(
        self,
        edit: sublime.Edit,
        new_name: str = "",
        placeholder: str = "",
        position: Optional[int] = None,
        event: Optional[dict] = None,
        point: Optional[int] = None
    ) -> None:
        if position is None:
            tmp_pos = get_position(self.view, event, point)
            if tmp_pos is None:
                return
            pos = tmp_pos
            if new_name:
                return self._do_rename(pos, new_name)
            else:
                session = self.best_session("{}.prepareProvider".format(self.capability))
                if session:
                    params = text_document_position_params(self.view, pos)
                    request = Request("textDocument/prepareRename", params, self.view, progress=True)
                    self.event = event
                    session.send_request(request, lambda r: self.on_prepare_result(r, pos), self.on_prepare_error)
                else:
                    # trigger InputHandler manually
                    raise TypeError("required positional argument")
        else:
            if new_name:
                return self._do_rename(position, new_name)
            else:
                # trigger InputHandler manually
                raise TypeError("required positional argument")

    def _do_rename(self, position: int, new_name: str) -> None:
        session = self.best_session(self.capability)
        if not session:
            return
        position_params = text_document_position_params(self.view, position)
        params = {
            "textDocument": position_params["textDocument"],
            "position": position_params["position"],
            "newName": new_name,
        }
        request = Request("textDocument/rename", params, self.view, progress=True)
        session.send_request(request, functools.partial(self._on_rename_result_async, session))

    def _on_rename_result_async(self, session: Session, response: Any) -> None:
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

    def on_prepare_result(self, response: Any, pos: int) -> None:
        if response is None:
            sublime.error_message("The current selection cannot be renamed")
            return
        # It must be a dict at this point.
        if "placeholder" in response:
            placeholder = response["placeholder"]
            r = response["range"]
        else:
            placeholder = self.view.substr(self.view.word(pos))
            r = response
        region = range_to_region(r, self.view)
        args = {"placeholder": placeholder, "position": region.a, "event": self.event}
        self.view.run_command("lsp_symbol_rename", args)

    def on_prepare_error(self, error: Any) -> None:
        sublime.error_message("Rename error: {}".format(error["message"]))

    def _get_relative_path(self, file_path: str) -> str:
        wm = windows.lookup(self.view.window())
        if not wm:
            return file_path
        base_dir = wm.get_project_path(file_path)
        return os.path.relpath(file_path, base_dir) if base_dir else file_path

    def _render_rename_panel(
        self,
        changes_per_uri: Dict[str, List[TextEditTuple]],
        total_changes: int,
        file_count: int
    ) -> None:
        wm = windows.lookup(self.view.window())
        if not wm:
            return
        panel = wm.panel_manager and wm.panel_manager.ensure_rename_panel()
        if not panel:
            return
        to_render = []  # type: List[str]
        for uri, changes in changes_per_uri.items():
            scheme, file = parse_uri(uri)
            if scheme == "file":
                to_render.append('{}:'.format(self._get_relative_path(file)))
            else:
                to_render.append('{}:'.format(uri))
            for edit in changes:
                start = edit[0]
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
