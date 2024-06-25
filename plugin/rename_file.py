from __future__ import annotations

from .core.open import open_file_uri
from .core.protocol import Notification, RenameFilesParams, Request, WorkspaceEdit
from .core.registry import LspTextCommand
from .core.url import parse_uri
from .core.views import did_open_text_document_params, uri_from_view
from pathlib import Path
from urllib.parse import urljoin
import os
import sublime
import sublime_plugin


class RenameFileInputHandler(sublime_plugin.TextInputHandler):
    def want_event(self) -> bool:
        return False

    def __init__(self, file_name: str) -> None:
        self.file_name = file_name

    def name(self) -> str:
        return "new_name"

    def placeholder(self) -> str:
        return self.file_name

    def initial_text(self) -> str:
        return self.placeholder()

    def validate(self, name: str) -> bool:
        return len(name) > 0

class LspRenameFileCommand(LspTextCommand):
    capability = 'workspace.fileOperations.willRename'

    def is_enabled(self):
        return True

    def want_event(self) -> bool:
        return False

    def input(self, args: dict) -> sublime_plugin.TextInputHandler | None:
        if "new_name" in args:
            return None
        return RenameFileInputHandler(Path(self.view.file_name() or "").name)

    def run(
        self,
        _edit: sublime.Edit,
        new_name: str = "", # new_name can be: FILE_NAME.xy OR ./FILE_NAME.xy OR ../../FILE_NAME.xy
        paths: str | None = None
    ) -> None:
        print('paths', paths)
        print('new_name', new_name)
        session = self.best_session("workspace.fileOperations.willRename")
        if not session:
            return
        current_file_path = self.view.file_name() or ''
        new_file_path = os.path.normpath(Path(current_file_path).parent / new_name)
        window = self.view.window()
        if os.path.exists(new_file_path) and window:
            window.status_message(f'Unable to Rename. File already exists')
            return
        rename_file_params: RenameFilesParams = {
            "files": [{
                "newUri": urljoin("file:", new_file_path),
                "oldUri": uri_from_view(self.view),
            }]
        }
        request = Request.willRenameFiles(rename_file_params)
        session.send_request(request, lambda res: self.handle(res, session.config.name, new_name, rename_file_params))

    def handle(self, res: WorkspaceEdit | None, session_name: str, new_name: str, rename_file_params: RenameFilesParams) -> None:
        window = self.view.window()
        session = self.session_by_name(session_name)
        if session and window:
            # LSP spec - Apply WorkspaceEdit before the files are renamed
            if res:
                session.apply_workspace_edit_async(res, is_refactoring=True)
            renamed_file = rename_file_params['files'][0]
            old_regions = [region for region in self.view.sel()]
            self.view.close() # LSP spec - send didClose for old file
            # actally rename the file, this will create a new file
            os.rename(
                parse_uri(renamed_file['oldUri'])[1],
                parse_uri(renamed_file['newUri'])[1]
            )
            # LSP spec - send didOpen for the new file
            open_file_uri(window, renamed_file['newUri']) \
                .then(lambda v: v and v.sel().add_all(old_regions))
        for session in self.sessions('workspace.fileOperations.didRename'):
            session.send_notification(Notification.didRenameFiles(rename_file_params))


