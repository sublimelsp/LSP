import sublime
import sublime_plugin

from .core.configurations import is_supported_syntax
from .core.edit import parse_text_edit
from .core.logging import debug
from .core.protocol import Request, Range, InsertTextFormat
from .core.registry import session_for_view, client_from_session, LSPViewEventListener
from .core.sessions import Session
from .core.settings import settings, client_configs
from .core.types import view2scope
from .core.typing import Any, List, Dict, Optional, Union
from .core.views import range_to_region
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


def format_completion(item: dict, change_id: Any) -> sublime.CompletionItem:
    item_kind = item.get("kind")
    if item_kind:
        kind = completion_kinds.get(item_kind, sublime.KIND_AMBIGUOUS)
    else:
        kind = sublime.KIND_AMBIGUOUS

    if item.get("deprecated", False):
        kind = (kind[0], '⚠', "⚠ {} - Deprecated".format(kind[2]))

    item["change_id"] = change_id

    return sublime.CompletionItem.command_completion(
        trigger=item["label"],
        command="lsp_select_completion_item",
        args=item,
        annotation=item.get('detail') or "",
        kind=kind
    )


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
            # this region was valid a few view.change_count() moments back ...
            edit_region = range_to_region(Range.from_lsp(text_edit['range']), self.view)
            # ... but this brings it to the present.
            edit_region = self.view.transform_region_from(edit_region, item["change_id"])
            selection = self.view.sel()
            primary_cursor_position = selection[0].b
            for region in reversed(selection):
                # For each selection region, apply the same removal as for the "primary" region.
                # To do that, translate, or offset, the LSP edit region into the non-"primary" regions.
                # The concept of "primary" is our own, and there is no mention of it in the LSP spec.
                translation = region.b - primary_cursor_position
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
            completionProvider = session.get_capability('completionProvider') or dict()  # type: dict
            # A language server may have an empty dict as CompletionOptions. In that case,
            # no trigger characters will be registered but we'll still respond to Sublime's
            # usual query for completions. So the explicit check for None is necessary.
            self.enabled = True

            trigger_chars = completionProvider.get(
                'triggerCharacters') or []
            if trigger_chars:
                self.register_trigger_chars(session, trigger_chars)
            # This is to make ST match with labels that have a weird prefix like a space character.
            self.view.settings().set("auto_complete_preserve_order", "none")

    def _view_language(self, config_name: str) -> Optional[str]:
        languages = self.view.settings().get('lsp_language')
        return languages.get(config_name) if languages else None

    def register_trigger_chars(self, session: Session, trigger_chars: List[str]) -> None:
        settings = self.view.settings()
        completion_triggers = settings.get('auto_complete_triggers', []) or []  # type: List[Dict[str, str]]
        base_scope = view2scope(self.view)
        for language in session.config.languages:
            if language.match(base_scope):
                completion_triggers.append({
                    'characters': "".join(trigger_chars),
                    'selector': '- comment'
                })
        settings.set('auto_complete_triggers', completion_triggers)

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
        client.send_request(
            Request.complete(text_document_position_params(self.view, locations[0])),
            lambda res: self.handle_response(res, completion_list, self.view.change_id()),
            lambda res: self.handle_error(res, completion_list))
        return completion_list

    def handle_response(self, response: Optional[Union[dict, List]],
                        completion_list: sublime.CompletionList, change_id: Any) -> None:
        response_items = []  # type: List[Dict]
        incomplete = False
        if isinstance(response, dict):
            response_items = response["items"] or []
            incomplete = response.get("isIncomplete", False)
        elif isinstance(response, list):
            response_items = response
        response_items = sorted(response_items, key=lambda item: item.get("sortText") or item["label"])

        flags = 0
        if settings.only_show_lsp_completions:
            flags |= sublime.INHIBIT_WORD_COMPLETIONS
            flags |= sublime.INHIBIT_EXPLICIT_COMPLETIONS

        if incomplete:
            flags |= sublime.DYNAMIC_COMPLETIONS
        resolve(completion_list, [format_completion(i, change_id) for i in response_items], flags)

    def handle_error(self, error: dict, completion_list: sublime.CompletionList) -> None:
        resolve(completion_list, [])
        sublime.status_message('Completion error: ' + str(error.get('message')))
