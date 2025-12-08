from __future__ import annotations
from .core.open import open_file_uri
from .core.promise import Promise
from .core.protocol import Notification, Request
from .core.registry import LspWindowCommand
from .core.types import match_file_operation_filters
from .core.url import filename_to_uri
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING
import sublime
import sublime_plugin
import weakref

if TYPE_CHECKING:
    from ..protocol import FileRename
    from ..protocol import WorkspaceEdit
    from .core.sessions import Session
    from collections.abc import Generator


class LspRenameFromSidebarOverrideCommand(LspWindowCommand):
    def is_enabled(self) -> bool:
        return True

    def run(self, paths: list[str] | None = None) -> None:
        old_path = paths[0] if paths else None
        if old_path:
            self.window.run_command('lsp_rename_path', {
                "old_path": old_path
            })


class RenamePathInputHandler(sublime_plugin.TextInputHandler):
    def __init__(self, path: str) -> None:
        self.path = path

    def name(self) -> str:
        return "new_name"

    def placeholder(self) -> str:
        return self.path

    def initial_text(self) -> str:
        return self.placeholder()

    def initial_selection(self) -> list[tuple[int, int]]:
        name = Path(self.path).stem
        return [(0, len(name))]

    def validate(self, path: str) -> bool:
        return len(path) > 0


class LspRenamePathCommand(LspWindowCommand):
    capability = 'workspace.fileOperations.willRename'

    def is_enabled(self) -> bool:
        return True

    def want_event(self) -> bool:
        return False

    def input(self, args: dict) -> sublime_plugin.TextInputHandler | None:
        if "new_name" in args:
            return None
        view = self.window.active_view()
        old_path = args.get('old_path') or view.file_name() if view else None
        return RenamePathInputHandler(Path(old_path or "").name)

    def run(self, new_name: str, old_path: str | None = None) -> None:
        view = self.window.active_view()
        old_path = old_path or view.file_name() if view else None
        if old_path is None:  # handle renaming buffers
            if view:
                view.set_name(new_name)
            return
        if new_name == old_path:
            return
        # new_name can be: FILE_NAME.xy OR ./FILE_NAME.xy OR ../../FILE_NAME.xy
        resolved_new_path = (Path(old_path).parent / new_name).resolve()
        new_path = str(resolved_new_path)
        if resolved_new_path.exists() and not self.is_case_change(old_path, new_path):
            self.window.status_message('Rename error: Target already exists')
            return
        sublime.set_timeout_async(lambda: self.run_async(old_path, new_path))

    def run_async(self, old_path: str, new_path: str) -> None:
        file_rename: FileRename = {
            "newUri": filename_to_uri(new_path),
            "oldUri": filename_to_uri(old_path)
        }
        Promise.all(list(self.create_will_rename_requests_async(file_rename))) \
            .then(lambda responses: self.handle_rename_async(responses)) \
            .then(lambda _: self.rename_path(old_path, new_path)) \
            .then(lambda success: self.notify_did_rename(file_rename) if success else None)

    def create_will_rename_requests_async(
        self, file_rename: FileRename
    ) -> Generator[Promise[tuple[WorkspaceEdit | None, weakref.ref[Session]]]]:
        for session in self.sessions():
            filters = session.get_capability('workspace.fileOperations.willRename.filters') or []
            if match_file_operation_filters(filters, file_rename['oldUri']):
                yield session.send_request_task(Request.willRenameFiles({'files': [file_rename]})) \
                    .then(partial(lambda weak_session, response: (response, weak_session), weakref.ref(session)))

    def is_case_change(self, path_a: str, path_b: str) -> bool:
        return path_a.lower() == path_b.lower() and Path(path_a).stat().st_ino == Path(path_b).stat().st_ino

    def handle_rename_async(self, responses: list[tuple[WorkspaceEdit | None, weakref.ref[Session]]]) -> Promise:
        promises: list[Promise] = []
        for response, weak_session in responses:
            if (session := weak_session()) and response:
                promises.append(session.apply_workspace_edit_async(response, is_refactoring=True))
        return Promise.all(promises)

    def rename_path(self, old: str, new: str) -> Promise[bool]:
        old_path = Path(old)
        new_path = Path(new)
        restore_files: list[tuple[str, tuple[int, int], list[sublime.Region]]] = []
        for view in self.window.views():
            if (file_name := view.file_name()) and file_name.startswith(str(old_path)):
                new_file_name = file_name.replace(str(old_path), str(new_path), 1)
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
            for file_name, group_index, selection in restore_files
        ]).then(lambda _: True)

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
