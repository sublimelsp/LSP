from .protocol import CompletionItemKind, Range
from .types import Settings
from .logging import debug
try:
    from typing import Tuple, Optional, Dict, List, Union
    assert Tuple and Optional and Dict and List and Union and Settings
except ImportError:
    pass


completion_item_kind_names = {v: k for k, v in CompletionItemKind.__dict__.items()}


def get_completion_hint(item: dict, settings: 'Settings') -> 'Optional[str]':
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
    return hint


def format_completion(item: dict, word_col: int, settings: 'Settings') -> 'Tuple[str, str]':
    # Sublime handles snippets automatically, so we don't have to care about insertTextFormat.
    if settings.prefer_label_over_filter_text:
        trigger = item["label"]
    else:
        trigger = item.get("filterText") or item["label"]

    hint = get_completion_hint(item, settings)

    # label is an alternative for insertText if neither textEdit nor insertText is provided
    replacement = text_edit_text(item, word_col) or item.get("insertText") or trigger

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
        else:
            debug("replacement prefix does not match trigger!")
            replacement = item.get("insertText") or trigger

    if len(replacement) > 0 and replacement[0] == '$':  # sublime needs leading '$' escaped.
        replacement = '\\$' + replacement[1:]
    # only return trigger with a hint if available
    return "\t  ".join((trigger, hint)) if hint else trigger, replacement


def text_edit_text(item: dict, word_col: int) -> 'Optional[str]':
    text_edit = item.get('textEdit')
    if text_edit:
        edit_range, edit_text = text_edit.get("range"), text_edit.get("newText")
        if edit_range and edit_text:
            edit_range = Range.from_lsp(edit_range)

            debug('textEdit from col {}, {} applied at col {}'.format(
                edit_range.start.col, edit_range.end.col, word_col))

            if edit_range.start.col <= word_col:
                # if edit starts at current word, we can use it.
                # if edit starts before current word, use the whole thing and we'll fix it up later.
                return edit_text

    return None


def parse_completion_response(response: 'Optional[Union[Dict,List]]'):
    items = []  # type: List[Dict]
    if isinstance(response, dict):
        items = response["items"] or []
    elif isinstance(response, list):
        items = response
    items = sorted(items, key=lambda item: item.get("sortText") or item["label"])
    return items
