from __future__ import annotations
from .core.open import open_file_uri
from .core.protocol import Notification, RenameFilesParams, Request, WorkspaceEdit
from .core.registry import LspWindowCommand
from .core.types import match_file_operation_filters
from pathlib import Path
from urllib.parse import urljoin
import os
import sublime
import sublime_plugin


class LspRenameFromSidebarOverride(LspWindowCommand):
    def is_enabled(self):
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
        name, _ext = os.path.splitext(self.path)
        return [(0, len(name))]

    def validate(self, path: str) -> bool:
        return len(path) > 0


class LspRenamePathCommand(LspWindowCommand):
    capability = 'workspace.fileOperations.willRename'

    def is_enabled(self):
        return True

    def want_event(self) -> bool:
        return False

    def input(self, args: dict) -> sublime_plugin.TextInputHandler | None:
        if "new_name" in args:
            return None
        view = self.window.active_view()
        old_path = view.file_name() if view else None
        return RenamePathInputHandler(Path(old_path or "").name)

    def run(
        self,
        new_name: str,  # new_name can be: FILE_NAME.xy OR ./FILE_NAME.xy OR ../../FILE_NAME.xy
        old_path: str | None = None,
    ) -> None:
        session = self.session()
        view = self.window.active_view()
        old_path = old_path or view.file_name() if view else None
        if old_path is None:  # handle renaming buffers
            if view:
                view.set_name(new_name)
            return
        new_path = os.path.normpath(Path(old_path).parent / new_name)
        if os.path.exists(new_path):
            self.window.status_message('Unable to Rename. Already exists')
            return
        rename_file_params: RenameFilesParams = {
            "files": [{
                "newUri": urljoin("file:", new_path),
                "oldUri": urljoin("file:", old_path),
            }]
        }
        file_operation_options = session.get_capability('workspace.fileOperations.willRename') if session else None
        if session and file_operation_options and match_file_operation_filters(file_operation_options, old_path, view):
            request = Request.willRenameFiles(rename_file_params)
            session.send_request(
                request,
                lambda res: self.handle(res, session.config.name, old_path, new_path, rename_file_params, view)
            )
        else:
            self.rename_path(old_path, new_path)
            self.notify_did_rename(rename_file_params, new_path, view)

    def handle(self, res: WorkspaceEdit | None, session_name: str,
               old_path: str, new_path: str, rename_file_params: RenameFilesParams, view: sublime.View | None) -> None:
        if session := self.session_by_name(session_name):
            # LSP spec - Apply WorkspaceEdit before the files are renamed
            if res:
                session.apply_workspace_edit_async(res, is_refactoring=True)
            self.rename_path(old_path, new_path)
            self.notify_did_rename(rename_file_params, new_path, view)

    def rename_path(self, old_path: str, new_path: str) -> None:
        old_regions: list[sublime.Region] = []
        if view := self.window.find_open_file(old_path):
            view.run_command('save', {'async': False})
            old_regions = [region for region in view.sel()]
            view.close()  # LSP spec - send didClose for the old file
        new_dir = Path(new_path).parent
        if not new_dir.exists():
            os.makedirs(new_dir)
        isdir = os.path.isdir(old_path)
        try:
            os.rename(old_path, new_path)
        except Exception:
            sublime.status_message("Unable to rename")
        if isdir:
            for v in self.window.views():
                file_name = v.file_name()
                if file_name and file_name.startswith(old_path):
                    v.retarget(file_name.replace(old_path, new_path))
        if os.path.isfile(new_path):
            def restore_regions(v: sublime.View | None) -> None:
                if not v:
                    return
                v.sel().clear()
                v.sel().add_all(old_regions)

            # LSP spec - send didOpen for the new file
            open_file_uri(self.window, new_path).then(restore_regions)

    def notify_did_rename(self, rename_file_params: RenameFilesParams, path: str, view: sublime.View | None):
        for s in self.sessions():
            file_operation_options = s.get_capability('workspace.fileOperations.didRename')
            if file_operation_options and match_file_operation_filters(file_operation_options, path, view):
                s.send_notification(Notification.didRenameFiles(rename_file_params))
