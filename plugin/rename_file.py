from __future__ import annotations

from .core.aio import run_on_main_thread
from .core.edit import show_summary_message
from .core.logging import debug
from .core.open import open_file_uri
from .core.protocol import Error
from .core.protocol import Request
from .core.registry import LspWindowCommand
from .core.types import match_file_operation_filters
from .core.url import filename_to_uri
from .edit import prompt_for_workspace_edits
from functools import partial
from pathlib import Path
from typing import Any
from typing import TYPE_CHECKING
from typing import TypedDict
from typing_extensions import NotRequired
import asyncio
import sublime
import sublime_plugin

if TYPE_CHECKING:
    from ..protocol import FileRename


class RenamePathInputHandler(sublime_plugin.TextInputHandler):

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def name(self) -> str:
        return "new_name"

    def placeholder(self) -> str:
        return self.path.name

    def initial_text(self) -> str:
        return self.placeholder()

    def initial_selection(self) -> list[tuple[int, int]]:
        return [(0, len(self.path.stem))]

    def validate(self, path: str) -> bool:
        return len(path) > 0


class LspRenamePathInputArgs(TypedDict):
    paths: NotRequired[list[str]]
    new_name: NotRequired[str]
    prompt_workspace_edits: NotRequired[bool]


class LspRenamePathCommand(LspWindowCommand):

    capability = 'workspace.fileOperations.willRename'

    @staticmethod
    def is_case_change(path_a: str, path_b: str) -> bool:
        return path_a.lower() == path_b.lower() and Path(path_a).stat().st_ino == Path(path_b).stat().st_ino

    def is_visible(self, **kwargs: dict[str, Any]) -> bool:
        return self.is_enabled()

    def want_event(self) -> bool:
        return False

    def input(self, args: LspRenamePathInputArgs) -> sublime_plugin.TextInputHandler | None:
        if "new_name" in args:
            return None
        if paths := args.get('paths'):  # command was called from side bar context menu
            return RenamePathInputHandler(paths[0])
        if (view := self.window.active_view()) and (file_name := view.file_name()):
            return RenamePathInputHandler(file_name)
        return RenamePathInputHandler("")

    async def run(self, new_name: str, paths: list[str] | None = None, prompt_workspace_edits: bool = True) -> None:
        old_path = paths[0] if paths else None
        view = self.window.active_view()
        if old_path is None and view:
            old_path = view.file_name()
        if old_path is None:  # handle renaming buffers
            if view:
                view.set_name(new_name)
            return
        # new_name can be: FILE_NAME.xy OR ./FILE_NAME.xy OR ../../FILE_NAME.xy
        resolved_new_path = (Path(old_path).parent / new_name).resolve()
        new_path = str(resolved_new_path)
        if new_path == old_path:
            return
        if resolved_new_path.exists() and not self.is_case_change(old_path, new_path):
            self.window.status_message('Rename error: Target already exists')
            return
        file_rename: FileRename = {
            "newUri": filename_to_uri(new_path),
            "oldUri": filename_to_uri(old_path)
        }
        if prompt_workspace_edits:
            label = f"Rename {Path(old_path).name} -> {new_name}"
            if not await self.apply_will_rename_edits(file_rename, label):
                return
        if await self.rename_path(old_path, new_path) and (mgr := self.manager()):
            mgr.notify_did_rename_files([file_rename])

    async def apply_will_rename_edits(self, file_rename: FileRename, label: str) -> bool:
        """
        Request and apply the WorkspaceEdit from the workspace/willRenameFiles request.

        Returns whether the file rename should proceed.
        """
        sessions = [
            session for session in self.sessions()
            if match_file_operation_filters(
                session.get_capability('workspace.fileOperations.willRename.filters') or [], file_rename['oldUri'])
        ]
        responses = await asyncio.gather(
            *(session.request(Request.willRenameFiles({'files': [file_rename]})) for session in sessions))
        for session, response in zip(sessions, responses):
            if not response:
                continue
            if isinstance(response, Error):
                debug(f'LSP: Error response during rename: {response}')
                return False
            if not await prompt_for_workspace_edits(session, response, label=label):
                return False
            summary = await session.apply_workspace_edit(response, label=label, is_refactoring=True)
            show_summary_message(session.window, *summary)
            return True
        # Ensure file rename even if all WorkspaceEdit responses are empty
        return True

    async def rename_path(self, old: str, new: str) -> bool:
        old_path = Path(old)
        new_path = Path(new)
        restore_files: list[tuple[str, tuple[int, int], list[sublime.Region]]] = []
        active_view = self.window.active_view()
        last_active_view: str | None = active_view.file_name() if active_view else None
        for view in reversed(self.window.views()):
            if (file_name := view.file_name()) and file_name.startswith(str(old_path)):
                new_file_name = file_name.replace(str(old_path), str(new_path), 1)
                if view == active_view:
                    last_active_view = new_file_name
                restore_files.append((new_file_name, self.window.get_view_index(view), list(view.sel())))
                if view.is_dirty():
                    await run_on_main_thread(partial(view.run_command, 'save', {'async': False}))
                view.close()  # LSP spec - send didClose for the old file
        if (new_dir := new_path.parent) and not new_dir.exists():
            new_dir.mkdir(parents=True)
        try:
            old_path.rename(new_path)  # noqa: ASYNC240
        except Exception as error:
            sublime.status_message(f"Rename error: {error}")
            return False
        for file_name, group, selection in reversed(restore_files):
            self.restore_view(selection, group, await open_file_uri(self.window, file_name, group=group[0]))
        self.focus_view(last_active_view)
        return True

    def restore_view(self, selection: list[sublime.Region], group: tuple[int, int], view: sublime.View | None) -> None:
        if not view:
            return
        group_index, tab_index = group
        self.window.set_view_index(view, group_index, tab_index)
        if selection:
            view.sel().clear()
            view.sel().add_all(selection)

    def focus_view(self, path: str | None) -> None:
        if path and (view := self.window.find_open_file(path)):
            self.window.focus_view(view)
