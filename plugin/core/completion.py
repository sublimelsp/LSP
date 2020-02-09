import sublime
from .typing import Tuple, Optional, Dict, List, Union


completion_kinds = {
    1: (sublime.KIND_ID_MARKUP, "Ξ", "Text"),
    2: (sublime.KIND_ID_FUNCTION, "λ", "Method"),
    3: (sublime.KIND_ID_FUNCTION, "λ", "Function"),
    4: (sublime.KIND_ID_FUNCTION, "c", "Constructor"),
    5: (sublime.KIND_ID_VARIABLE, "f", "Field"),
    6: (sublime.KIND_ID_VARIABLE, "v", "Variable"),
    7: (sublime.KIND_ID_TYPE, "c", "Class"),
    8: (sublime.KIND_ID_TYPE, "i", "Interface"),
    9: (sublime.KIND_ID_NAMESPACE, "◪", "Module"),
    10: (sublime.KIND_ID_VARIABLE, "ρ", "Property"),
    11: (sublime.KIND_ID_VARIABLE, "u", "Unit"),
    12: (sublime.KIND_ID_VARIABLE, "ν", "Value"),
    13: (sublime.KIND_ID_TYPE, "ε", "Enum"),
    14: (sublime.KIND_ID_KEYWORD, "κ", "Keyword"),
    15: (sublime.KIND_ID_SNIPPET, "s", "Snippet"),
    16: (sublime.KIND_ID_AMBIGUOUS, "c", "Color"),
    17: (sublime.KIND_ID_AMBIGUOUS, "#", "File"),
    18: (sublime.KIND_ID_AMBIGUOUS, "⇢", "Reference"),
    19: (sublime.KIND_ID_AMBIGUOUS, "ƒ", "Folder"),
    20: (sublime.KIND_ID_TYPE, "ε", "EnumMember"),
    21: (sublime.KIND_ID_VARIABLE, "π", "Constant"),
    22: (sublime.KIND_ID_TYPE, "s", "Struct"),
    23: (sublime.KIND_ID_FUNCTION, "e", "Event"),
    24: (sublime.KIND_ID_KEYWORD, "ο", "Operator"),
    25: (sublime.KIND_ID_TYPE, "τ", "Type Parameter")
}


def format_completion(item: dict) -> sublime.CompletionItem:
    trigger = item.get('label') or ""
    annotation = item.get('detail') or ""
    kind = sublime.KIND_AMBIGUOUS

    item_kind = item.get("kind")
    if item_kind:
        kind = completion_kinds.get(item_kind, sublime.KIND_AMBIGUOUS)

    is_deprecated = item.get("deprecated", False)
    if is_deprecated:
        list_kind = list(kind)
        list_kind[1] = '⚠'
        list_kind[2] = "⚠ {} - Deprecated".format(list_kind[2])
        kind = tuple(list_kind)  # type: ignore

    return sublime.CompletionItem.command_completion(
        trigger,
        command="lsp_select_completion_item",
        args={
            "item": item
        },
        annotation=annotation,
        kind=kind
    )


def parse_completion_response(response: Optional[Union[Dict, List]]) -> Tuple[List[Dict], bool]:
    items = []  # type: List[Dict]
    is_incomplete = False
    if isinstance(response, dict):
        items = response["items"] or []
        is_incomplete = response.get("isIncomplete", False)
    elif isinstance(response, list):
        items = response
    items = sorted(items, key=lambda item: item.get("sortText") or item["label"])
    return items, is_incomplete
