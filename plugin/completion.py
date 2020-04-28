import html
import sublime
import sublime_plugin

from .core.configurations import is_supported_syntax
from .core.edit import parse_text_edit
from .core.logging import debug
from .core.protocol import Request, InsertTextFormat
from .core.registry import session_for_view, client_from_session, LSPViewEventListener
from .core.settings import settings, client_configs
from .core.typing import Any, List, Dict, Optional, Union, Iterable, Tuple
from .core.views import text_document_position_params


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


_changes_since_sent = []  # type: List[sublime.TextChange]
_change_id = None  # type: Any


class LspSelectCompletionItemCommand(sublime_plugin.TextCommand):
    """
    This command must handle four different kinds of LSP completion items:

    1) plaintext + insertText   (e.g. pyls)
    2) plaintext + textEdit     (e.g. intelephense)
    3) snippet   + insertText   (???)
    4) snippet   + textEdit     (e.g. clangd, intelephense)

    For cases (3) and (4) we are forced to use the "insert_snippet" command.
    """

    def run(self, edit: sublime.Edit, **item: Any) -> None:
        # Is it a textEdit or an insertText?
        text_edit = item.get('textEdit')
        if text_edit:
            new_text = text_edit['newText']
            old_region = item.pop("native_region")  # type: Tuple[int, int]
            # This brings the historic sublime.Region to the present.
            global _change_id
            edit_region = self.view.transform_region_from(sublime.Region(old_region[0], old_region[1]), _change_id)
            selection = self.view.sel()
            primary_cursor_position = selection[0].b
            for region in reversed(selection):
                # For each selection region, apply the same removal as for the "primary" region.
                # To do that, translate, or offset, the LSP edit region into the non-"primary" regions.
                # The concept of "primary" is our own, and there is no mention of it in the LSP spec.
                translation = region.b - primary_cursor_position
                # We will assume that the user was typing the same characters.
                self.view.erase(edit, sublime.Region(edit_region.a + translation, edit_region.b + translation))
        else:
            new_text = item.get('insertText') or item['label']

        # Is it a plaintext or a snippet?
        if item.get("insertTextFormat", InsertTextFormat.PlainText) == InsertTextFormat.Snippet:
            self.view.run_command("insert_snippet", {"contents": new_text})
        else:
            self.view.run_command("insert", {"characters": new_text})

        # import statements, etc. some servers only return these after a resolve.
        additional_edits = item.get('additionalTextEdits')
        if additional_edits:
            self.apply_additional_edits(additional_edits)
        else:
            self.do_resolve(item)

    def do_resolve(self, item: dict) -> None:
        session = session_for_view(self.view, 'completionProvider', self.view.sel()[0].begin())
        if not session:
            return

        client = client_from_session(session)
        if not client:
            return

        completion_provider = session.get_capability('completionProvider')
        has_resolve_provider = completion_provider and completion_provider.get('resolveProvider', False)
        if has_resolve_provider:
            client.send_request(Request.resolveCompletionItem(item), self.handle_resolve_response)

    def handle_resolve_response(self, response: Optional[dict]) -> None:
        if response:
            additional_edits = response.get('additionalTextEdits')
            if additional_edits:
                self.apply_additional_edits(additional_edits)

    def apply_additional_edits(self, additional_edits: List[dict]) -> None:
        edits = list(parse_text_edit(additional_edit) for additional_edit in additional_edits)
        debug('applying additional edits:', edits)
        self.view.run_command("lsp_apply_document_edit", {'changes': edits})
        sublime.status_message('Applied additional edits for completion')


def resolve(completion_list: sublime.CompletionList, items: List[sublime.CompletionItem], flags: int = 0) -> None:
    # Resolve the promise on the main thread to prevent any sort of data race for _set_target (see sublime_plugin.py).
    sublime.set_timeout(lambda: completion_list.set_completions(items, flags))


class CompletionHandler(LSPViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.initialized = False
        self.enabled = False
        self._request_in_flight = False

    def __del__(self) -> None:
        settings = self.view.settings()
        triggers = settings.get("auto_complete_triggers")  # type: List[Dict[str, str]]
        triggers = [trigger for trigger in triggers if 'server' not in trigger]
        settings.set("auto_complete_triggers", triggers)

    @classmethod
    def is_applicable(cls, view_settings: dict) -> bool:
        if 'completion' in settings.disabled_capabilities:
            return False

        syntax = view_settings.get('syntax')
        return is_supported_syntax(syntax, client_configs.all) if syntax else False

    def initialize(self) -> None:
        self.initialized = True
        session = session_for_view(self.view, 'completionProvider')
        if session:
            capability = session.get_capability('completionProvider') or dict()  # type: dict
            # A language server may have an empty dict as CompletionOptions. In that case,
            # no trigger characters will be registered but we'll still respond to Sublime's
            # usual query for completions. So the explicit check for None is necessary.
            self.enabled = True
            trigger_chars = capability.get('triggerCharacters') or []
            settings = self.view.settings()
            if trigger_chars:
                completion_triggers = settings.get('auto_complete_triggers') or []  # type: List[Dict[str, str]]
                completion_triggers.append({
                    'characters': "".join(trigger_chars),
                    # Heuristics: Don't auto-complete in comments, and don't trigger auto-complete when we're at the
                    # end of a string. We *do* want to trigger auto-complete in strings because of languages like
                    # Bash and some language servers are allowing the user to auto-complete file-system files in
                    # things like import statements. We may want to move this to the LSP.sublime-settings.
                    'selector': "- comment - punctuation.definition.string.end",
                    'server': session.config.name
                })
                settings.set('auto_complete_triggers', completion_triggers)
            # This is to make ST match with labels that have a weird prefix like a space character.
            settings.set("auto_complete_preserve_order", "none")

    def on_text_changed(self, changes: Iterable[sublime.TextChange]) -> None:
        if self._request_in_flight:
            global _changes_since_sent
            _changes_since_sent.extend(changes)

    def on_query_completions(self, prefix: str, locations: List[int]) -> Optional[sublime.CompletionList]:
        if not self.initialized:
            self.initialize()
        if not self.enabled:
            return None
        client = client_from_session(session_for_view(self.view, 'completionProvider', locations[0]))
        if not client:
            return None
        self.manager.documents.purge_changes(self.view)
        completion_list = sublime.CompletionList()
        self._request_in_flight = True
        client.send_request(
            Request.complete(text_document_position_params(self.view, locations[0])),
            lambda res: self.handle_response(res, completion_list),
            lambda res: self.handle_error(res, completion_list))
        return completion_list

    def format_completion(self, item: dict) -> sublime.CompletionItem:
        # This is a hot function. Don't do heavy computations or IO in this function.
        item_kind = item.get("kind")
        if item_kind:
            kind = completion_kinds.get(item_kind, sublime.KIND_AMBIGUOUS)
        else:
            kind = sublime.KIND_AMBIGUOUS

        if item.get("deprecated", False):
            kind = (kind[0], '⚠', "⚠ {} - Deprecated".format(kind[2]))

        text_edit = item.get("textEdit")
        if text_edit:
            r = text_edit["range"]
            start, end = r["start"], r["end"]
            # From the LSP spec: the range of the edit must be a single line range and it must contain the position at
            # which completion has been requested.
            row, start_col_utf16, end_col_utf16 = start["line"], start["character"], end["character"]
            # The TextEdit from the language server might apply to an old version of the buffer. The user may have
            # entered more characters in the meantime.
            global _changes_since_sent
            for change in _changes_since_sent:
                # Thus, adjust the range for each buffer change.
                start_col_utf16, end_col_utf16 = transform_region(start_col_utf16, end_col_utf16, change)
            # We don't have to use region_to_range. That function clamps the unreliable input, but having unreliable
            # (row, col) points for completions is pretty much disastrous. So we'll assume the (row, col) points are
            # correct. Blame the language server if the regions are incorrect.
            convert = self.view.text_point_utf16
            item["native_region"] = (convert(row, start_col_utf16), convert(row, end_col_utf16))

        lsp_label = item["label"]
        lsp_filter_text = item.get("filterText")
        lsp_detail = item.get("detail") or ""
        if lsp_filter_text:
            st_trigger = lsp_filter_text
            st_annotation = lsp_label
            st_details = html.escape(lsp_detail.replace('\n', ' '))
        else:
            st_trigger = lsp_label
            st_annotation = lsp_detail
            st_details = ''

        return sublime.CompletionItem.command_completion(
            trigger=st_trigger,
            command="lsp_select_completion_item",
            args=item,
            annotation=st_annotation,
            kind=kind,
            details=st_details
        )

    def handle_response(self, response: Optional[Union[dict, List]], completion_list: sublime.CompletionList) -> None:
        self._request_in_flight = False
        response_items = []  # type: List[Dict]
        flags = 0
        if settings.only_show_lsp_completions:
            flags |= sublime.INHIBIT_WORD_COMPLETIONS
            flags |= sublime.INHIBIT_EXPLICIT_COMPLETIONS
        if isinstance(response, dict):
            response_items = response["items"] or []
            if response.get("isIncomplete", False):
                flags |= sublime.DYNAMIC_COMPLETIONS
        elif isinstance(response, list):
            response_items = response
        global _change_id
        _change_id = self.view.change_id()
        response_items = sorted(response_items, key=lambda item: item.get("sortText") or item["label"])
        items = list(map(self.format_completion, response_items))
        _changes_since_sent.clear()
        resolve(completion_list, items, flags)

    def handle_error(self, error: dict, completion_list: sublime.CompletionList) -> None:
        self._request_in_flight = False
        _changes_since_sent.clear()
        resolve(completion_list, [])
        sublime.status_message('Completion error: ' + str(error.get('message')))


def transform_region(col_a: int, col_b: int, change: sublime.TextChange) -> Tuple[int, int]:
    """
    Here be dragons. Given an LSP region, and a change to the text buffer, transform the region into the coordinate
    space after that change has been applied. Note that this mirrors the algorithm that View.transform_region_from uses
    internally.

    Returns the adjusted col_a and col_b.
    """
    a = change.a.col_utf16
    b = change.b.col_utf16
    length_utf16 = len(change.str.encode("UTF-16")) // 2
    if a <= col_a <= b:
        col_a = a
    elif a > col_a:
        col_a += length_utf16 + b - a
    if a <= col_b < b:
        col_b = a
    elif a >= col_b:
        col_a += length_utf16 + b - a
    return col_a, col_b
