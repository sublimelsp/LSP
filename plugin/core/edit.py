from .typing import List, Dict, Any, Iterable, Tuple
from .url import uri_to_filename
import operator

TextEdit = Tuple[Tuple[int, int], Tuple[int, int], str]


def parse_workspace_edit(workspace_edit: Dict[str, Any]) -> Dict[str, List[TextEdit]]:
    changes = {}  # type: Dict[str, List[TextEdit]]
    if 'changes' in workspace_edit:
        for uri, file_changes in workspace_edit.get('changes', {}).items():
            changes[uri_to_filename(uri)] = list(parse_text_edit(change) for change in file_changes)
    if 'documentChanges' in workspace_edit:
        for document_change in workspace_edit.get('documentChanges', []):
            uri = document_change.get('textDocument').get('uri')
            changes[uri_to_filename(uri)] = list(parse_text_edit(change) for change in document_change.get('edits'))
    return changes


def parse_range(range: Dict[str, int]) -> Tuple[int, int]:
    return range['line'], range['character']


def parse_text_edit(text_edit: Dict[str, Any]) -> TextEdit:
    return (
        parse_range(text_edit['range']['start']),
        parse_range(text_edit['range']['end']),
        text_edit.get('newText', '')
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
