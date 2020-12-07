from .logging import debug
from .open import open_file
from .promise import Promise
from .types import ClientConfig
from .typing import List, Dict, Any, Iterable, Optional, Tuple
from functools import partial
import operator
import sublime


# tuple of start, end, newText, version
TextEdit = Tuple[Tuple[int, int], Tuple[int, int], str, Optional[int]]


def parse_workspace_edit(config: ClientConfig, workspace_edit: Dict[str, Any]) -> Dict[str, List[TextEdit]]:
    changes = {}  # type: Dict[str, List[TextEdit]]
    raw_changes = workspace_edit.get('changes')
    if isinstance(raw_changes, dict):
        for uri, file_changes in raw_changes.items():
            path = config.map_server_uri_to_client_path(uri)
            changes[path] = list(parse_text_edit(change) for change in file_changes)
    document_changes = workspace_edit.get('documentChanges')
    if isinstance(document_changes, list):
        for document_change in document_changes:
            if 'kind' in document_change:
                debug('Ignoring unsupported "resourceOperations" edit type')
                continue
            uri = document_change.get('textDocument').get('uri')
            version = document_change.get('textDocument').get('version')
            text_edit = list(parse_text_edit(change, version) for change in document_change.get('edits'))
            path = config.map_server_uri_to_client_path(uri)
            changes.setdefault(path, []).extend(text_edit)
    return changes


def parse_range(range: Dict[str, int]) -> Tuple[int, int]:
    return range['line'], range['character']


def parse_text_edit(text_edit: Dict[str, Any], version: int = None) -> TextEdit:
    return (
        parse_range(text_edit['range']['start']),
        parse_range(text_edit['range']['end']),
        # Strip away carriage returns -- SublimeText takes care of that.
        text_edit.get('newText', '').replace("\r", ""),
        version
    )


def sort_by_application_order(changes: Iterable[TextEdit]) -> List[TextEdit]:
    # The spec reads:
    # > However, it is possible that multiple edits have the same start position: multiple
    # > inserts, or any number of inserts followed by a single remove or replace edit. If
    # > multiple inserts have the same position, the order in the array defines the order in
    # > which the inserted strings appear in the resulting text.
    # So we sort by start position. But if multiple text edits start at the same position,
    # we use the index in the array as the key.

    return list(sorted(changes, key=operator.itemgetter(0)))


def apply_workspace_edit(window: sublime.Window, changes: Dict[str, List[TextEdit]]) -> Promise:
    """Apply workspace edits. This function must be called from the main thread!"""
    return Promise.all([open_file(window, fn).then(partial(_apply_edits, edits)) for fn, edits in changes.items()])


def _apply_edits(edits: List[TextEdit], view: Optional[sublime.View]) -> None:
    if view and view.is_valid():
        # Text commands run blocking. After this call has returned the changes are applied.
        view.run_command("lsp_apply_document_edit", {"changes": edits})
