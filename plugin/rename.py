from .core.edit import apply_workspace_edit
from .core.edit import parse_workspace_edit
from .core.edit import TextEdit
from .core.panels import ensure_panel
from .core.panels import PanelName
from .core.protocol import Range
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.registry import windows
from .core.types import PANEL_FILE_REGEX, PANEL_LINE_REGEX
from .core.typing import Any, Optional, Dict, List
from .core.views import first_selection, range_to_region, get_line
from .core.views import text_document_position_params
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

    def input(self, args: dict) -> Optional[sublime_plugin.TextInputHandler]:
        if "new_name" not in args:
            placeholder = args.get("placeholder", "")
            if not placeholder:
                point = args.get("point")
                # guess the symbol name
                if not isinstance(point, int):
                    region = first_selection(self.view)
                    if not region:
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
        if session:
            params = text_document_position_params(self.view, position)
            params["newName"] = new_name
            session.send_request(
                Request("textDocument/rename", params, self.view, progress=True),
                # This has to run on the main thread due to calling apply_workspace_edit
                lambda r: sublime.set_timeout(lambda: self.on_rename_result(r))
            )

    def on_rename_result(self, response: Any) -> None:
        window = self.view.window()
        if window:
            if response:
                changes = parse_workspace_edit(response)
                file_count = len(changes.keys())
                if file_count > 1:
                    total_changes = sum(map(len, changes.values()))
                    message = "Replace {} occurrences across {} files?".format(total_changes, file_count)
                    choice = sublime.yes_no_cancel_dialog(message, "Replace", "Dry Run")
                    if choice == sublime.DIALOG_YES:
                        apply_workspace_edit(window, changes)
                    elif choice == sublime.DIALOG_NO:
                        self._render_rename_panel(changes, total_changes, file_count)
                else:
                    apply_workspace_edit(window, changes)
            else:
                window.status_message('Nothing to rename')

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
        region = range_to_region(Range.from_lsp(r), self.view)
        args = {"placeholder": placeholder, "position": region.a, "event": self.event}
        self.view.run_command("lsp_symbol_rename", args)

    def on_prepare_error(self, error: Any) -> None:
        sublime.error_message("Rename error: {}".format(error["message"]))

    def _get_relative_path(self, file_path: str) -> str:
        window = self.view.window()
        if not window:
            return file_path
        base_dir = windows.lookup(window).get_project_path(file_path)
        if base_dir:
            return os.path.relpath(file_path, base_dir)
        else:
            return file_path

    def _render_rename_panel(self, changes: Dict[str, List[TextEdit]], total_changes: int, file_count: int) -> None:
        window = self.view.window()
        if not window:
            return
        panel = ensure_rename_panel(window)
        if not panel:
            return
        to_render = []  # type: List[str]
        for file, file_changes in changes.items():
            to_render.append('{}:'.format(self._get_relative_path(file)))
            for edit in file_changes:
                start = edit[0]
                line_content = get_line(self.view.window(), file, start[0])
                to_render.append('{:>5}:{:<4} {}'.format(start[0] + 1, start[1] + 1, line_content))
            to_render.append("")  # this adds a spacing between filenames
        characters = "\n".join(to_render)
        base_dir = windows.lookup(window).get_project_path(self.view.file_name() or "")
        panel.settings().set("result_base_dir", base_dir)
        panel.run_command("lsp_clear_panel")
        window.run_command("show_panel", {"panel": "output.rename"})
        fmt = "{} changes across {} files.\n\n{}"
        panel.run_command('append', {
            'characters': fmt.format(total_changes, file_count, characters),
            'force': True,
            'scroll_to_end': False
        })


def ensure_rename_panel(window: sublime.Window) -> Optional[sublime.View]:
    return ensure_panel(
        window=window,
        name=PanelName.Rename,
        result_file_regex=PANEL_FILE_REGEX,
        result_line_regex=PANEL_LINE_REGEX,
        syntax="Packages/LSP/Syntaxes/References.sublime-syntax"
    )
