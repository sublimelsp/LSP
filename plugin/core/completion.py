from .protocol import CompletionItemKind, Range
from .types import Settings
try:
    from typing import Tuple, Optional, Dict, List, Union
    assert Tuple and Optional and Dict and List and Union
except ImportError:
    pass


completion_item_kind_names = {v: k for k, v in CompletionItemKind.__dict__.items()}


def format_completion(item: dict, last_col: int, settings: 'Settings') -> 'Tuple[str, str]':
    # Sublime handles snippets automatically, so we don't have to care about insertTextFormat.
    if settings.prefer_label_over_filter_text:
        trigger = item["label"]
    else:
        trigger = item.get("filterText") or item["label"]
    # choose hint based on availability and user preference
    hint = None
    if settings.completion_hint_type == "auto":
        hint = item.get("detail")
        if not hint:
            kind = item.get("kind")
            if kind:
                hint = completion_item_kind_names[kind]
    elif settings.completion_hint_type == "detail":
        hint = item.get("detail")
    elif settings.completion_hint_type == "kind":
        kind = item.get("kind")
        if kind:
            hint = completion_item_kind_names.get(kind)
    # label is an alternative for insertText if neither textEdit nor insertText is provided
    replacement = text_edit_text(item, last_col) or item.get("insertText") or trigger

    if replacement[0] != trigger[0]:
        # fix some common cases when server sends different start on label and replacement.
        if replacement[0] == '$':
            trigger = '$' + trigger  # add missing $
        elif replacement[0] == '-':
            trigger = '-' + trigger  # add missing -
        elif trigger[0] == '$':
            trigger = trigger[1:]  # remove leading $
        elif trigger[0] == ' ' or trigger[0] == '•':
            trigger = trigger[1:]  # remove clangd insertion indicator

    if len(replacement) > 0 and replacement[0] == '$':  # sublime needs leading '$' escaped.
        replacement = '\\$' + replacement[1:]
    # only return trigger with a hint if available
    return "\t  ".join((trigger, hint)) if hint else trigger, replacement


def text_edit_text(item: dict, last_col: int) -> 'Optional[str]':
    text_edit = item.get("textEdit")
    if text_edit:
        edit_range, edit_text = text_edit.get("range"), text_edit.get("newText")
        if edit_range and edit_text:
            edit_range = Range.from_lsp(edit_range)

            if edit_range.start.col <= last_col:
                # sublime does not support explicit replacement with completion
                # at given range, but we try to trim the textEdit range and text
                # to the start location of the completion
                return edit_text[last_col - edit_range.start.col:]
    return None


def parse_completion_response(response: 'Optional[Union[Dict,List]]', last_col: int, settings: Settings):
    items = []  # type: List[Dict]
    if isinstance(response, dict):
        items = response["items"] or []
    elif isinstance(response, list):
        items = response
    items = sorted(items, key=lambda item: item.get("sortText") or item["label"])
    return list(format_completion(item, last_col, settings) for item in items)
