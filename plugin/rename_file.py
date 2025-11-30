from __future__ import annotations
from ..protocol import FileRename
from ..protocol import WorkspaceEdit
from .core.open import open_file_uri
from .core.promise import Promise
from .core.protocol import Notification, Request
from .core.registry import LspWindowCommand
from .core.sessions import Session
from .core.types import match_file_operation_filters
from .core.url import filename_to_uri, parse_uri
from pathlib import Path
import sublime
import sublime_plugin
import weakref


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
            self.window.status_message('Unable to Rename. Already exists')
            return
        file_rename: FileRename = {
            "newUri": filename_to_uri(new_path),
            "oldUri": filename_to_uri(old_path)
        }

        def create_request_async(session: Session) -> Promise[tuple[WorkspaceEdit | None, weakref.ref[Session]]]:
            return session.send_request_task(
                        Request.willRenameFiles({'files': [file_rename]})
                   ).then(lambda response: (response, weakref.ref(session)))

        sessions = [session for session in self.sessions() if match_file_operation_filters(
            session.get_capability('workspace.fileOperations.willRename'), file_rename['oldUri']
        )]
        promises = [create_request_async(session) for session in sessions]
        if promises:
            sublime.set_timeout_async(
                lambda: Promise.all(promises).then(lambda responses: self.handle_rename_async(responses, file_rename))
            )
        else:
            self.rename_path(file_rename)

    def is_case_change(self, path_a: str, path_b: str) -> bool:
        return path_a.lower() == path_b.lower() and Path(path_a).stat().st_ino == Path(path_b).stat().st_ino

    def handle_rename_async(self, responses: list[tuple[WorkspaceEdit | None, weakref.ref[Session]]],
                            file_rename: FileRename) -> None:
        for response, weak_session in responses:
            if (session := weak_session()) and response:
                session.apply_workspace_edit_async(response, is_refactoring=True) \
                    .then(lambda _: self.rename_path(file_rename))

    def rename_path(self, file_rename: FileRename) -> None:
        old_path = Path(parse_uri(file_rename['oldUri'])[1])
        new_path = Path(parse_uri(file_rename['newUri'])[1])
        old_regions: list[sublime.Region] = []
        if view := self.window.find_open_file(str(old_path)):
            view.run_command('save', {'async': False})
            old_regions = list(view.sel())
            view.close()  # LSP spec - send didClose for the old file
        new_dir = new_path.parent
        if not new_dir.exists():
            new_dir.mkdir()
        old_path_is_dir = old_path.is_dir()
        try:
            old_path.rename(new_path)
        except Exception:
            sublime.status_message("Unable to rename")
            return
        if old_path_is_dir:
            for view in self.window.views():
                file_name = view.file_name()
                if file_name and file_name.startswith(str(old_path)):
                    view.retarget(file_name.replace(str(old_path), str(new_path)))
        if new_path.is_file():
            def restore_regions(view: sublime.View | None) -> None:
                if not view:
                    return
                view.sel().clear()
                view.sel().add_all(old_regions)

            # LSP spec - send didOpen for the new file
            open_file_uri(self.window, str(new_path)).then(restore_regions) \
                .then(lambda _: self.notify_did_rename(file_rename))

    def notify_did_rename(self, file_rename: FileRename):
        for session in self.sessions():
            file_operations = session.get_capability('workspace.fileOperations.didRename')
            if file_operations and match_file_operation_filters(file_operations, file_rename['oldUri']):
                session.send_notification(Notification.didRenameFiles({'files': [file_rename]}))
