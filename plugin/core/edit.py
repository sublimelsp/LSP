from __future__ import annotations
from ...protocol import AnnotatedTextEdit
from ...protocol import Position
from ...protocol import TextEdit
from ...protocol import WorkspaceEdit
from .logging import debug
from .promise import Promise
from .protocol import UINT_MAX
from typing import Dict, List, Optional, Tuple, TypedDict, Union
from typing_extensions import NotRequired
import sublime


WorkspaceChanges = Dict[str, Tuple[List[Union[TextEdit, AnnotatedTextEdit]], Optional[str], Optional[int]]]


class WorkspaceEditSummary(TypedDict):
    total_changes: int
    updated_files: int
    created_files: NotRequired[int]
    renamed_files: NotRequired[int]
    deleted_files: NotRequired[int]


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
                if 'snippet' in edit:
                    debug('Ignoring unsupported SnippetTextEdit')
                    continue
                description = change_annotations[id_]['label'] if (id_ := edit.get('annotationId')) else label
                # Note that if the WorkspaceEdit contains multiple AnnotatedTextEdit with different labels for the same
                # URI, we only show the first label in the undo menu, because all edits are combined into a single
                # buffer modification in the lsp_apply_document_edit command.
                changes.setdefault(uri, ([], description, version))[0].append(edit)
    else:
        raw_changes = workspace_edit.get('changes')
        if isinstance(raw_changes, dict):
            for uri, edits in raw_changes.items():
                changes[uri] = (edits, label, None)
    return changes


def parse_range(range: Position) -> tuple[int, int]:
    return range['line'], min(UINT_MAX, range['character'])


def apply_text_edits(
    view: sublime.View,
    edits: list[TextEdit] | None,
    *,
    label: str | None = None,
    process_placeholders: bool | None = False,
    required_view_version: int | None = None
) -> Promise[sublime.View | None]:
    if not edits:
        return Promise.resolve(view)
    if not view.is_valid():
        print('LSP: ignoring edits due to view not being open')
        return Promise.resolve(None)
    view.run_command(
        'lsp_apply_document_edit',
        {
            'changes': edits,
            'label': label,
            'process_placeholders': process_placeholders,
            'required_view_version': required_view_version,
        }
    )
    # Resolving from the next message loop iteration guarantees that the edits have already been applied in the main
    # thread, and that we’ve received view changes in the asynchronous thread.
    return Promise(lambda resolve: sublime.set_timeout_async(lambda: resolve(view if view.is_valid() else None)))
