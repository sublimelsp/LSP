from __future__ import annotations
from ..protocol import WorkspaceEdit
from ..protocol import RenameFilesParams
from .core.open import open_file_uri
from .core.protocol import Notification, Request
from .core.registry import LspWindowCommand
from .core.types import match_file_operation_filters
from .core.url import filename_to_uri
from pathlib import Path
import os
import sublime
import sublime_plugin


class LspRenameFromSidebarOverride(LspWindowCommand):
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
        name, _ext = os.path.splitext(self.path)
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
            self.window.status_message('Unable to Rename. Already exists')
            return
        new_path_uri = filename_to_uri(new_path)
        old_path_uri = filename_to_uri(old_path)
        rename_file_params: RenameFilesParams = {
            "files": [{
                "newUri": new_path_uri,
                "oldUri": old_path_uri
            }]
        }
        session = self.session()
        file_operation_options = session.get_capability('workspace.fileOperations.willRename') if session else None
        if session and file_operation_options and match_file_operation_filters(file_operation_options, old_path_uri):
            request = Request.willRenameFiles(rename_file_params)
            session.send_request(
                request,
                lambda response: self.handle_response_async(response, session.config.name,
                                                             old_path, new_path, rename_file_params)
            )
        else:
            self.rename_path(old_path, new_path)
            self.notify_did_rename(rename_file_params)

    def is_case_change(self, path_a: str, path_b: str) -> bool:
        if path_a.lower() != path_b.lower():
            return False
        if os.stat(path_a).st_ino != os.stat(path_b).st_ino:
            return False
        return True

    def handle_response_async(self, response: WorkspaceEdit | None, session_name: str,
                               old_path: str, new_path: str, rename_file_params: RenameFilesParams) -> None:
        def on_workspace_edits_applied(_) -> None:
            self.rename_path(old_path, new_path)
            self.notify_did_rename(rename_file_params)

        if (session := self.session_by_name(session_name)) and response:
            session.apply_workspace_edit_async(response, is_refactoring=True).then(on_workspace_edits_applied)

    def rename_path(self, old_path: str, new_path: str) -> None:
        old_regions: list[sublime.Region] = []
        if view := self.window.find_open_file(old_path):
            view.run_command('save', {'async': False})
            old_regions = list(view.sel())
            view.close()  # LSP spec - send didClose for the old file
        new_dir = Path(new_path).parent
        if not new_dir.exists():
            os.makedirs(new_dir)
        is_directory = os.path.isdir(old_path)
        try:
            os.rename(old_path, new_path)
        except Exception:
            sublime.status_message("Unable to rename")
            return
        if is_directory:
            for view in self.window.views():
                file_name = view.file_name()
                if file_name and file_name.startswith(old_path):
                    view.retarget(file_name.replace(old_path, new_path))
        if os.path.isfile(new_path):
            def restore_regions(view: sublime.View | None) -> None:
                if not view:
                    return
                view.sel().clear()
                view.sel().add_all(old_regions)

            # LSP spec - send didOpen for the new file
            open_file_uri(self.window, new_path).then(restore_regions)

    def notify_did_rename(self, rename_file_params: RenameFilesParams):
        for session in self.sessions():
            file_operation_options = session.get_capability('workspace.fileOperations.didRename')
            old_uri = rename_file_params['files'][0]['oldUri']
            if file_operation_options and match_file_operation_filters(file_operation_options, old_uri):
                session.send_notification(Notification.didRenameFiles(rename_file_params))
