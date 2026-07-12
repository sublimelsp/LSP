from __future__ import annotations

from ...protocol import AnnotatedTextEdit
from ...protocol import ApplyWorkspaceEditResult
from ...protocol import CreateFile
from ...protocol import DeleteFile
from ...protocol import Position
from ...protocol import RenameFile
from ...protocol import SnippetTextEdit
from ...protocol import TextDocumentEdit
from ...protocol import TextEdit
from ...protocol import WorkspaceEdit
from .logging import debug
from .logging import printf
from .promise import Promise
from .protocol import UINT_MAX
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple
from typing import TypedDict
from typing import Union
from typing_extensions import NotRequired
from typing_extensions import TypeGuard
import sublime

WorkspaceChanges = Dict[str, Tuple[List[Union[TextEdit, AnnotatedTextEdit, SnippetTextEdit]], Optional[str], Optional[int]]]  # noqa: E501


class WorkspaceEditSummary(TypedDict):
    total_changes: int
    edited_files: int
    created_files: NotRequired[int]
    renamed_files: NotRequired[int]
    deleted_files: NotRequired[int]


def is_text_document_edit(
    document_change: TextDocumentEdit | CreateFile | RenameFile | DeleteFile
) -> TypeGuard[TextDocumentEdit]:
    return 'edits' in document_change


def is_create_file(document_change: TextDocumentEdit | CreateFile | RenameFile | DeleteFile) -> TypeGuard[CreateFile]:
    return document_change.get('kind') == 'create'


def is_rename_file(document_change: TextDocumentEdit | CreateFile | RenameFile | DeleteFile) -> TypeGuard[RenameFile]:
    return document_change.get('kind') == 'rename'


def is_delete_file(document_change: TextDocumentEdit | CreateFile | RenameFile | DeleteFile) -> TypeGuard[DeleteFile]:
    return document_change.get('kind') == 'delete'


def is_snippet_text_edit(edit: TextEdit | AnnotatedTextEdit | SnippetTextEdit) -> TypeGuard[SnippetTextEdit]:
    return 'snippet' in edit


def parse_workspace_edit(workspace_edit: WorkspaceEdit, label: str | None = None) -> WorkspaceChanges:
    changes: WorkspaceChanges = {}
    document_changes = workspace_edit.get('documentChanges')
    if isinstance(document_changes, list):
        change_annotations = workspace_edit.get('changeAnnotations', {})
        for document_change in document_changes:
            if 'kind' in document_change:
                # TODO: Support resource operations (create/rename/remove)
                debug('Ignoring unsupported "resourceOperations" edit type')
                continue
            text_document = document_change["textDocument"]
            uri = text_document['uri']
            version = text_document.get('version')
            edits = document_change.get('edits')
            for edit in edits:
                description = change_annotations[id_]['label'] if (id_ := edit.get('annotationId')) else label
                # Note that if the WorkspaceEdit contains multiple AnnotatedTextEdit with different labels for the same
                # URI, we only show the first label in the undo menu, because all edits are combined into a single
                # buffer modification in the lsp_apply_document_edit command.
                changes.setdefault(uri, ([], description, version))[0].append(edit)
    else:
        raw_changes = workspace_edit.get('changes')
        if isinstance(raw_changes, dict):
            for uri, edits in raw_changes.items():
                changes[uri] = (edits, label, None)  # pyright: ignore[reportArgumentType]
    return changes


def parse_lsp_position(position: Position) -> tuple[int, int]:
    return position['line'], min(UINT_MAX, position['character'])


def apply_text_edits(
    view: sublime.View,
    edits: Sequence[TextEdit | AnnotatedTextEdit | SnippetTextEdit],
    *,
    label: str | None = None,
    process_placeholders: bool = False,
    required_view_version: int | None = None
) -> Promise[sublime.View | None]:
    if not edits:
        return Promise.resolve(view)
    if not view.is_valid():
        printf('ignoring edits due to view not being open')
        return Promise.resolve(None)
    if process_placeholders:
        # Deprecated because SnippetTextEdit is now part of the LSP 3.18 specs.
        printf(
            'The "process_placeholders" argument for the apply_text_edits function is deprecated.',
            'Convert the TextEdit into a SnippetTextEdit instead.'
        )
        view.run_command(
            'lsp_apply_document_edit',
            {
                'changes': edits,
                'label': label,
                'process_placeholders': True,
                'required_view_version': required_view_version,
            }
        )
    elif required_view_version is None or required_view_version == view.change_count():
        view.run_command('lsp_apply_text_document_edit', {'edits': edits, 'label': label})
    # Resolving from the next message loop iteration guarantees that the edits have already been applied in the main
    # thread, and that we've received view changes in the asynchronous thread.
    return Promise(lambda resolve: sublime.set_timeout_async(lambda: resolve(view if view.is_valid() else None)))


def show_summary_message(
    window: sublime.Window, result: ApplyWorkspaceEditResult, summary: WorkspaceEditSummary
) -> None:
    if result['applied']:
        message = f"Applied {summary['total_changes']} changes in {summary['edited_files']} files"
    else:
        message = "Error while applying WorkspaceEdit"
        if failure_reason := result.get('failureReason'):
            message += f": {failure_reason}"
    # a 300ms timeout prevents "Detect indentation: ..." status message from overriding the summary status message
    sublime.set_timeout(lambda: window.status_message(message), 300)
