from __future__ import annotations

from .core.aio import run_coroutine
from .core.edit import show_summary_message
from .core.protocol import Error
from .core.protocol import Request
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.views import range_to_region
from .core.views import text_document_position_params
from .edit import prompt_for_workspace_edits
from typing import TYPE_CHECKING
from typing_extensions import TypeGuard
import sublime
import sublime_plugin

if TYPE_CHECKING:
    from ..protocol import PrepareRenameParams
    from ..protocol import PrepareRenameResult
    from ..protocol import Range
    from ..protocol import RenameParams
    from .core.sessions import Session

PREPARE_RENAME_CAPABILITY = "renameProvider.prepareProvider"


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
        session_name: str | None = None,
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
        point = get_position(self.view, point=args.get('point'))
        if point is None:
            # Defer to "run" and trigger rename.
            return None
        session = self._get_prepare_rename_session(point, args.get('session_name'))
        if session and "placeholder" not in args:
            # Defer to "run" and trigger "prepare" request.
            return None
        placeholder = args.get("placeholder", "")
        if not placeholder:
            # guess the symbol name
            placeholder = self.view.substr(self.view.word(point))
        return RenameSymbolInputHandler(self.view, placeholder)

    def run(
        self,
        edit: sublime.Edit,
        new_name: str = "",
        placeholder: str = "",
        session_name: str | None = None,
        event: dict | None = None,
        point: int | None = None
    ) -> None:
        location = get_position(self.view, event, point)
        session = self._get_prepare_rename_session(point, session_name)
        if new_name or placeholder or not session:
            if location is not None and new_name:
                run_coroutine(self._do_rename(location, placeholder, new_name, session))
                return
            # Trigger InputHandler manually.
            raise TypeError("required positional argument")
        if location is None:
            return
        run_coroutine(self._do_rename_with_prepare_provider(location, session))

    def _get_prepare_rename_session(self, point: int | None, session_name: str | None) -> Session | None:
        return self.session_by_name(session_name, PREPARE_RENAME_CAPABILITY) if session_name \
            else self.best_session(PREPARE_RENAME_CAPABILITY, point)

    async def _do_rename_with_prepare_provider(self, pos: int, session: Session) -> None:
        if listener := self.get_listener():
            await listener.purge_changes()
        params: PrepareRenameParams = {
            **text_document_position_params(self.view, pos)
        }
        response = await session.request(Request.prepareRename(params, self.view, progress=True))
        if isinstance(response, Error):
            sublime.error_message(f"Rename error: {response}")
            return
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
        args = {"placeholder": placeholder, "point": pos, "session_name": session.config.name}
        self.view.run_command("lsp_symbol_rename", args)

    async def _do_rename(self, position: int, old_name: str, new_name: str, preferred_session: Session | None) -> None:
        session = preferred_session or self.best_session(self.capability, position)
        if not session:
            return
        position_params = text_document_position_params(self.view, position)
        params: RenameParams = {
            "textDocument": position_params["textDocument"],
            "position": position_params["position"],
            "newName": new_name,
        }
        response = await session.request(Request.rename(params, self.view, progress=True))
        if isinstance(response, Error):
            sublime.error_message(f"Rename error: {response}")
            return
        if not response:
            session.window.status_message('Nothing to rename')
            return
        if await prompt_for_workspace_edits(session, response, label=f"Rename {old_name} → {new_name}"):
            summary = await session.apply_workspace_edit(response, is_refactoring=True)
            show_summary_message(session.window, *summary)


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
