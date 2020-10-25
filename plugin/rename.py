import sublime
import sublime_plugin
from .core.edit import apply_workspace_edit
from .core.edit import parse_workspace_edit
from .core.protocol import Range
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.typing import Any, Optional
from .core.views import range_to_region
from .core.views import text_document_position_params
from .documents import is_at_word


class RenameSymbolInputHandler(sublime_plugin.TextInputHandler):
    def __init__(self, view: sublime.View, placeholder: str) -> None:
        self.view = view
        self._placeholder = placeholder

    def name(self) -> str:
        return "new_name"

    def placeholder(self) -> str:
        if self._placeholder:
            return self._placeholder
        return self.get_current_symbol_name()

    def initial_text(self) -> str:
        return self.placeholder()

    def validate(self, name: str) -> bool:
        return len(name) > 0

    def get_current_symbol_name(self) -> str:
        pos = get_position(self.view)
        current_name = self.view.substr(self.view.word(pos))
        # Is this check necessary?
        if not current_name:
            current_name = ""
        return current_name


class LspSymbolRenameCommand(LspTextCommand):

    capability = 'renameProvider'

    def is_enabled(self, event: Optional[dict] = None) -> bool:
        if self.best_session("renameProvider.prepareProvider"):
            # The language server will tell us if the selection is on a valid token.
            return True
        # TODO: check what kind of scope we're in.
        return super().is_enabled(event) and is_at_word(self.view, event)

    def input(self, args: dict) -> Optional[sublime_plugin.TextInputHandler]:
        if "new_name" not in args:
            return RenameSymbolInputHandler(self.view, args.get("placeholder", ""))
        else:
            return None

    def run(
        self,
        edit: sublime.Edit,
        new_name: str = "",
        placeholder: str = "",
        position: Optional[int] = None,
        event: Optional[dict] = None
    ) -> None:
        if position is None:
            if new_name:
                return self._do_rename(get_position(self.view, event), new_name)
            else:
                session = self.best_session("{}.prepareProvider".format(self.capability))
                if session:
                    params = text_document_position_params(self.view, get_position(self.view, event))
                    request = Request.prepareRename(params, self.view)
                    self.event = event

                    def run_async() -> None:
                        assert session  # TODO: How to make mypy shut up about an Optional[Session]?
                        session.send_request(request, self.on_prepare_result, self.on_prepare_error)

                    sublime.set_timeout_async(run_async)
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

            def run_async() -> None:
                assert session  # TODO: How to make mypy shut up about an Optional[Session]?
                session.send_request(
                    Request.rename(params, self.view),
                    # This has to run on the main thread due to calling apply_workspace_edit
                    lambda r: sublime.set_timeout(lambda: self.on_rename_result(r))
                )

            sublime.set_timeout_async(run_async)

    def on_rename_result(self, response: Any) -> None:
        window = self.view.window()
        if window:
            if response:
                apply_workspace_edit(window, parse_workspace_edit(response))
            else:
                window.status_message('No rename edits returned')

    def on_prepare_result(self, response: Any) -> None:
        if response is None:
            sublime.error_message("The current selection cannot be renamed")
            return
        # It must be a dict at this point.
        if "placeholder" in response:
            placeholder = response["placeholder"]
            r = response["range"]
        else:
            placeholder = ""
            r = response
        region = range_to_region(Range.from_lsp(r), self.view)
        args = {"placeholder": placeholder, "position": region.a, "event": self.event}
        self.view.run_command("lsp_symbol_rename", args)

    def on_prepare_error(self, error: Any) -> None:
        sublime.error_message("Rename error: {}".format(error["message"]))
