import sublime
import sublime_plugin
from .protocol import CompletionItemKind, InsertTextFormat, Range
from .types import Settings
from .logging import debug
try:
    from typing import Tuple, Optional, Dict, List, Union
    assert Tuple and Optional and Dict and List and Union and Settings
except ImportError:
    pass


completion_item_kind_names = {v: k for k, v in CompletionItemKind.__dict__.items()}


compleiton_kinds = {
    1: (sublime.KIND_ID_MARKUP, "Ξ", "Text"),
    2: (sublime.KIND_ID_FUNCTION, "λ", "Method"),
    3: (sublime.KIND_ID_FUNCTION, "λ", "Function"),
    4: (sublime.KIND_ID_FUNCTION, "c", "Constructor"),
    5: (sublime.KIND_ID_VARIABLE, "f", "Field"),
    6: (sublime.KIND_ID_VARIABLE, "v", "Variable"),
    7: (sublime.KIND_ID_TYPE, "⊂", "Class"),
    8: (sublime.KIND_ID_TYPE, "i", "Interface"),
    9: (sublime.KIND_ID_NAMESPACE, "❒", "Module"),
    10: (sublime.KIND_ID_VARIABLE, "ρ", "Property"),
    11: (sublime.KIND_ID_VARIABLE, "u", "Unit"),
    12: (sublime.KIND_ID_VARIABLE, "ν", "Value"),
    13: (sublime.KIND_ID_TYPE, "ε", "Enum"),
    14: (sublime.KIND_ID_KEYWORD, "ㆁ", "Keyword"),
    15: (sublime.KIND_ID_SNIPPET, "s", "Snippet"),
    16: (sublime.KIND_ID_AMBIGUOUS, "c", "Color"),
    17: (sublime.KIND_ID_AMBIGUOUS, "ʃ", "File"),
    18: (sublime.KIND_ID_AMBIGUOUS, "⇢", "Reference"),
    19: (sublime.KIND_ID_AMBIGUOUS, "ʃ", "Folder"),
    20: (sublime.KIND_ID_TYPE, "ε", "EnumMember"),
    21: (sublime.KIND_ID_VARIABLE, "π", "Constant"),
    22: (sublime.KIND_ID_TYPE, "s", "Struct"),
    23: (sublime.KIND_ID_FUNCTION, "e", "Event"),
    24: (sublime.KIND_ID_KEYWORD, "ο", "Operator"),
    25: (sublime.KIND_ID_TYPE, "τ", "Type Parameter")
}


def format_completion(item: dict, word_col: int, settings: 'Settings' = None) -> 'Tuple[str, str]':
    trigger = item.get('label')
    annotation = item.get('detail', "")
    kind = sublime.KIND_AMBIGUOUS

    item_kind = item.get("kind")
    if item_kind:
        kind = compleiton_kinds.get(item_kind)

    is_deprecated = item.get("deprecated", False)
    if is_deprecated:
        list_kind = list(kind)
        list_kind[1] = '⚠'
        list_kind[2] = "⚠ {} - Deprecated".format(list_kind[2])
        kind = tuple(list_kind)

    completion = item.get('insertText') or item.get('label')

    insert_text_format = item.get("insertTextFormat")
    if insert_text_format == InsertTextFormat.Snippet:
        return sublime.CompletionItem.snippet_completion(trigger, completion, annotation, kind)

    return sublime.CompletionItem.command_completion(
        trigger,
        command="lsp_select_completion_item",
        args={
            "item": item
        },
        annotation=annotation,
        kind=kind
    )

    return sublime.CompletionItem(trigger, annotation, completion, kind=kind)


def text_edit_text(item: dict, word_col: int) -> 'Optional[str]':
    text_edit = item.get('textEdit')
    if text_edit:
        edit_range, edit_text = text_edit.get("range"), text_edit.get("newText")
        if edit_range and edit_text:
            edit_range = Range.from_lsp(edit_range)

            # debug('textEdit from col {}, {} applied at col {}'.format(
            #     edit_range.start.col, edit_range.end.col, word_col))

            if edit_range.start.col <= word_col:
                # if edit starts at current word, we can use it.
                # if edit starts before current word, use the whole thing and we'll fix it up later.
                return edit_text

    return None


def parse_completion_response(response: 'Optional[Union[Dict,List]]') -> 'Tuple[List[Dict], bool]':
    items = []  # type: List[Dict]
    is_incomplete = False
    if isinstance(response, dict):
        items = response["items"] or []
        is_incomplete = response.get("isIncomplete", False)
    elif isinstance(response, list):
        items = response
    items = sorted(items, key=lambda item: item.get("sortText") or item["label"])
    return items, is_incomplete
