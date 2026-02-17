from __future__ import annotations

from .core.edit import show_summary_message
from .core.logging import debug
from .core.open import open_file_uri
from .core.promise import Promise
from .core.protocol import Error
from .core.protocol import Notification
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
import sublime
import sublime_plugin
import weakref

if TYPE_CHECKING:
    from ..protocol import FileRename
    from ..protocol import WorkspaceEdit
    from .core.sessions import Session
    from collections.abc import Generator


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

    def is_enabled(self) -> bool:
        return True

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

    def run(self, new_name: str, paths: list[str] | None = None, prompt_workspace_edits: bool = True) -> None:
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
            rename_command_args: dict[str, Any] = {
                "paths": [old_path],
                "new_name": new_path,
                "prompt_workspace_edits": False
            }
            label = f"Rename {Path(old_path).name} -> {new_name}"
            sublime.set_timeout_async(lambda: self.prompt_rename_async(file_rename, label, rename_command_args))
            return
        self.rename_path(old_path, new_name).then(lambda success: self.on_rename_path(success, file_rename))

    def on_rename_path(self, success: bool, file_rename: FileRename) -> None:
        if success:
            self.notify_did_rename(file_rename)

    def prompt_rename_async(self, file_rename: FileRename, label: str, rename_command_args: dict[str, Any]) -> None:
        Promise.all(list(self.create_will_rename_requests_async(file_rename))) \
            .then(lambda responses: self.handle_rename_async(responses, label, rename_command_args))

    def create_will_rename_requests_async(
        self, file_rename: FileRename
    ) -> Generator[Promise[tuple[WorkspaceEdit | None | Error, weakref.ref[Session]]]]:
        for session in self.sessions():
            filters = session.get_capability('workspace.fileOperations.willRename.filters') or []
            if match_file_operation_filters(filters, file_rename['oldUri']):
                yield session.send_request_task(Request.willRenameFiles({'files': [file_rename]})) \
                    .then(partial(self.return_response_with_session, weakref.ref(session)))

    def return_response_with_session(
        self, weak_session: weakref.ref[Session], response: WorkspaceEdit | None | Error
    ) -> tuple[WorkspaceEdit | None | Error, weakref.ref[Session]]:
        return (response, weak_session)

    def handle_rename_async(self, responses: list[tuple[WorkspaceEdit | None | Error, weakref.ref[Session]]],
                            label: str, rename_command_args: dict[str, Any]) -> None:
        for response, weak_session in responses:
            if (session := weak_session()) and response:
                if isinstance(response, Error):
                    debug(f'LSP: Error response during rename: {response}')
                    return
                prompt_for_workspace_edits(session, response, label=label) \
                    .then(partial(self.on_prompt_for_workspace_edits_concluded, weak_session, response, label)) \
                    .then(lambda accepted: accepted and self.window.run_command('lsp_rename_path', rename_command_args))
                return
        # Ensure file rename even if all WorkspaceEdit responses are empty
        self.window.run_command('lsp_rename_path', rename_command_args)

    def on_prompt_for_workspace_edits_concluded(
        self, weak_session: weakref.ref[Session], response: WorkspaceEdit, label: str, accepted: bool,
    ) -> Promise[bool]:
        if accepted and (session := weak_session()):
            return session.apply_workspace_edit_async(response, label=label, is_refactoring=True) \
                .then(lambda summary: show_summary_message(session.window, summary)) \
                .then(lambda _: accepted)
        return Promise.resolve(False)

    def rename_path(self, old: str, new: str) -> Promise[bool]:
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
                    view.run_command('save', {'async': False})
                view.close()  # LSP spec - send didClose for the old file
        if (new_dir := new_path.parent) and not new_dir.exists():
            new_dir.mkdir(parents=True)
        try:
            old_path.rename(new_path)
        except Exception as error:
            sublime.status_message(f"Rename error: {error}")
            return Promise.resolve(False)
        return Promise.all([
            open_file_uri(self.window, file_name, group=group[0]).then(partial(self.restore_view, selection, group))
            for file_name, group, selection in reversed(restore_files)
        ]).then(lambda _: self.focus_view(last_active_view)).then(lambda _: True)

    def notify_did_rename(self, file_rename: FileRename) -> None:
        for session in self.sessions():
            filters = session.get_capability('workspace.fileOperations.didRename.filters') or []
            if filters and match_file_operation_filters(filters, file_rename['oldUri']):
                session.send_notification(Notification.didRenameFiles({'files': [file_rename]}))

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
