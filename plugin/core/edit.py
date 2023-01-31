from .logging import debug
from .open import open_file
from .promise import Promise
from .protocol import Position
from .protocol import TextEdit
from .protocol import UINT_MAX
from .protocol import WorkspaceEdit
from .typing import List, Dict, Optional, Tuple
from functools import partial
import sublime


# tuple of start, end, newText, version
TextEditTuple = Tuple[Tuple[int, int], Tuple[int, int], str, Optional[int]]


def parse_workspace_edit(workspace_edit: WorkspaceEdit) -> Dict[str, List[TextEditTuple]]:
    changes = {}  # type: Dict[str, List[TextEditTuple]]
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
            text_edit = list(parse_text_edit(change, version) for change in document_change.get('edits'))
            changes.setdefault(uri, []).extend(text_edit)
    else:
        raw_changes = workspace_edit.get('changes')
        if isinstance(raw_changes, dict):
            for uri, uri_changes in raw_changes.items():
                changes[uri] = list(parse_text_edit(change) for change in uri_changes)
    return changes


def parse_range(range: Position) -> Tuple[int, int]:
    return range['line'], min(UINT_MAX, range['character'])


def parse_text_edit(text_edit: TextEdit, version: Optional[int] = None) -> TextEditTuple:
    return (
        parse_range(text_edit['range']['start']),
        parse_range(text_edit['range']['end']),
        # Strip away carriage returns -- SublimeText takes care of that.
        text_edit.get('newText', '').replace("\r", ""),
        version
    )


def apply_workspace_edit(window: sublime.Window, changes: Dict[str, List[TextEditTuple]]) -> Promise:
    """
    DEPRECATED: Use session.apply_workspace_edit_async instead.
    """
    return Promise.all([open_file(window, uri).then(partial(apply_edits, edits)) for uri, edits in changes.items()])


def apply_edits(edits: List[TextEditTuple], view: Optional[sublime.View]) -> None:
    if view and view.is_valid():
        # Text commands run blocking. After this call has returned the changes are applied.
        view.run_command("lsp_apply_document_edit", {"changes": edits})
