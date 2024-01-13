from .logging import debug
from .protocol import Position
from .protocol import TextEdit
from .protocol import UINT_MAX
from .protocol import WorkspaceEdit
from .typing import List, Dict, Optional, Tuple
import sublime


WorkspaceChanges = Dict[str, Tuple[List[TextEdit], Optional[int]]]


def parse_workspace_edit(workspace_edit: WorkspaceEdit) -> WorkspaceChanges:
    changes = {}  # type: WorkspaceChanges
    document_changes = workspace_edit.get('documentChanges')
    if isinstance(document_changes, list):
        for document_change in document_changes:
            if 'kind' in document_change:
                # TODO: Support resource operations (create/rename/remove)
                debug('Ignoring unsupported "resourceOperations" edit type')
                continue
            text_document = document_change["textDocument"]
            uri = text_document['uri']
            version = text_document.get('version')
            edits = document_change.get('edits')
            changes.setdefault(uri, ([], version))[0].extend(edits)
    else:
        raw_changes = workspace_edit.get('changes')
        if isinstance(raw_changes, dict):
            for uri, edits in raw_changes.items():
                changes[uri] = (edits, None)
    return changes


def parse_range(range: Position) -> Tuple[int, int]:
    return range['line'], min(UINT_MAX, range['character'])


def apply_text_edits(
    view: sublime.View,
    edits: Optional[List[TextEdit]],
    *,
    process_placeholders: Optional[bool] = False,
    required_view_version: Optional[int] = None
) -> None:
    view.run_command(
        'lsp_apply_document_edit',
        {
            'changes': edits or [],
            'process_placeholders': process_placeholders,
            'required_view_version': required_view_version,
        }
    )
