import html
import mdpopups
import sublime
import sublime_plugin
import webbrowser

from .core.configurations import is_supported_syntax
from .core.edit import parse_text_edit
from .core.protocol import Request, InsertTextFormat, Range
from .core.registry import session_for_view, client_from_session, LSPViewEventListener
from .core.settings import settings, client_configs
from .core.typing import Any, List, Dict, Optional, Union, Generator
from .core.views import text_document_position_params, range_to_region, minihtml


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


class LspResolveDocsCommand(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit, index: int) -> None:
        item = CompletionHandler.completions[index]
        detail = minihtml(self.view, item.get('detail') or "")
        documentation = minihtml(self.view, item.get("documentation") or "")

        # don't show the detail in the cooperate AC popup if it is already shown in the AC details filed.
        self.is_detail_shown = bool(detail)
        minihtml_content = self.get_content(documentation, detail)
        self.show_popup(minihtml_content)

        if not detail or not documentation:
            # To make sure that the detail or documentation fields doesn't exist we need to resove the completion item.
            # If those fields appear after the item is resolved we show them in the popup.
            self.do_resolve(item)

    def get_content(self, documentation: str, detail: str) -> str:
        content = ""
        if detail and not self.is_detail_shown:
            content += "<div class='highlight' style='margin: 6px'>{}</div>".format(detail)
        if documentation:
            content += "<div style='margin: 6px'>{}</div>".format(documentation)
        return content

    def show_popup(self, minihtml_content: str) -> None:
        mdpopups.show_popup(
            self.view,
            minihtml_content,
            flags=sublime.COOPERATE_WITH_AUTO_COMPLETE,
            max_width=480,
            max_height=410,
            allow_code_wrap=True,
            on_navigate=self.on_navigate
        )

    def on_navigate(self, url: str) -> None:
        webbrowser.open(url)

    def do_resolve(self, item: dict) -> None:
        session = session_for_view(self.view, 'completionProvider.resolveProvider')
        if session:
            session.client.send_request(
                Request.resolveCompletionItem(item),
                lambda res: self.handle_resolve_response(res))

    def handle_resolve_response(self, item: Optional[dict]) -> None:
        if not item:
            return
        detail = minihtml(self.view, item.get('detail') or "")
        documentation = minihtml(self.view, item.get("documentation") or "")
        minihtml_content = self.get_content(documentation, detail)
        if self.view.is_popup_visible():
            self.update_popup(minihtml_content)
        else:
            self.show_popup(minihtml_content)

    def update_popup(self, minihtml_content: str) -> None:
        mdpopups.update_popup(self.view, minihtml_content)


class LspCompleteCommand(sublime_plugin.TextCommand):

    def handle_additional_edits(self, item: Dict[str, Any]) -> None:
        additional_edits = item.get('additionalTextEdits')
        if additional_edits:
            edits = [parse_text_edit(additional_edit) for additional_edit in additional_edits]
            self.view.run_command("lsp_apply_document_edit", {'changes': edits})


class LspCompleteInsertTextCommand(LspCompleteCommand):

    def run(self, edit: sublime.Edit, **item: Any) -> None:
        insert_text = item.get("insertText") or item["label"]
        if item.get("insertTextFormat", InsertTextFormat.PlainText) == InsertTextFormat.Snippet:
            self.view.run_command("insert_snippet", {"contents": insert_text})
        else:
            self.view.run_command("insert", {"characters": insert_text})
        self.handle_additional_edits(item)


class LspCompleteTextEditCommand(LspCompleteCommand):

    def run(self, edit: sublime.Edit, **item: Any) -> None:
        text_edit = item["textEdit"]
        new_text = text_edit['newText']
        edit_region = range_to_region(Range.from_lsp(text_edit['range']), self.view)
        if item.get("insertTextFormat", InsertTextFormat.PlainText) == InsertTextFormat.Snippet:
            for region in self.translated_regions(edit_region):
                self.view.erase(edit, region)
            self.view.run_command("insert_snippet", {"contents": new_text})
        else:
            for region in self.translated_regions(edit_region):
                # NOTE: Cannot do .replace, because ST will select the replacement.
                self.view.erase(edit, region)
                self.view.insert(edit, region.a, new_text)
        self.handle_additional_edits(item)

    def translated_regions(self, edit_region: sublime.Region) -> Generator[sublime.Region, None, None]:
        selection = self.view.sel()
        primary_cursor_position = selection[0].b
        for region in reversed(selection):
            # For each selection region, apply the same removal as for the "primary" region.
            # To do that, translate, or offset, the LSP edit region into the non-"primary" regions.
            # The concept of "primary" is our own, and there is no mention of it in the LSP spec.
            translation = region.b - primary_cursor_position
            translated_edit_region = sublime.Region(edit_region.a + translation, edit_region.b + translation)
            yield translated_edit_region


def resolve(completion_list: sublime.CompletionList, items: List[sublime.CompletionItem], flags: int = 0) -> None:
    # Resolve the promise on the main thread to prevent any sort of data race for _set_target (see sublime_plugin.py).
    sublime.set_timeout(lambda: completion_list.set_completions(items, flags))


class CompletionHandler(LSPViewEventListener):
    completions = []  # type: List[dict]

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.initialized = False
        self.enabled = False

    def __del__(self) -> None:
        settings = self.view.settings()
        triggers = settings.get("auto_complete_triggers") or []  # type: List[Dict[str, str]]
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

    def on_post_text_command(self, command: str, args: dict) -> None:
        if not self.view.is_popup_visible():
            return
        if command in ["hide_auto_complete", "move", "commit_completion"] or 'delete' in command:
            # hide the popup when `esc` or arrows are pressed pressed
            self.view.hide_popup()

    def on_query_completions(self, prefix: str, locations: List[int]) -> Optional[sublime.CompletionList]:
        if not self.initialized:
            self.initialize()
        if not self.enabled:
            return None
        session = session_for_view(self.view, 'completionProvider', locations[0])
        if not session:
            return None
        client = client_from_session(session)
        if not client:
            return None
        self.manager.documents.purge_changes(self.view)
        completion_list = sublime.CompletionList()
        capability = session.get_capability('completionProvider') or {}
        can_resolve_completion_items = bool(capability.get('resolveProvider', False))
        client.send_request(
            Request.complete(text_document_position_params(self.view, locations[0])),
            lambda res: self.handle_response(res, completion_list, can_resolve_completion_items),
            lambda res: self.handle_error(res, completion_list))
        return completion_list

    def format_completion(self, item: dict, index: int, can_resolve_completion_items: bool) -> sublime.CompletionItem:
        # This is a hot function. Don't do heavy computations or IO in this function.
        item_kind = item.get("kind")
        if item_kind:
            kind = completion_kinds.get(item_kind, sublime.KIND_AMBIGUOUS)
        else:
            kind = sublime.KIND_AMBIGUOUS

        if item.get("deprecated", False):
            kind = (kind[0], '⚠', "⚠ {} - Deprecated".format(kind[2]))

        lsp_label = item["label"]
        lsp_filter_text = item.get("filterText")
        lsp_detail = html.escape(item.get("detail", "").replace('\n', ' '))

        if lsp_filter_text and lsp_filter_text != lsp_label:
            st_trigger = lsp_filter_text
            st_annotation = lsp_label
        else:
            st_trigger = lsp_label
            st_annotation = ""

        st_details = ""
        if can_resolve_completion_items or item.get("documentation"):
            st_details += "<a href='subl:lsp_resolve_docs {{\"index\": {}}}'>More</a>".format(index)
            st_details += " | " if lsp_detail else ""

        st_details += "<p>{}</p>".format(lsp_detail)

        # NOTE: Some servers return "textEdit": null. We have to check if it's truthy.
        if item.get("textEdit"):
            # text edits are complex and can do anything. Use a command completion.
            completion = sublime.CompletionItem.command_completion(
                trigger=st_trigger,
                command="lsp_complete_text_edit",
                args=item,
                annotation=st_annotation,
                kind=kind,
                details=st_details)
            completion.flags = sublime.COMPLETION_FLAG_KEEP_PREFIX
        elif item.get("additionalTextEdits"):
            # It's an insertText, but additionalEdits requires us to use a command completion.
            completion = sublime.CompletionItem.command_completion(
                trigger=st_trigger,
                command="lsp_complete_insert_text",
                args=item,
                annotation=st_annotation,
                kind=kind,
                details=st_details)
        else:
            # A snippet completion suffices for insertText with no additionalTextEdits.
            snippet = item.get("insertText") or item["label"]
            if item.get("insertTextFormat", InsertTextFormat.PlainText) == InsertTextFormat.PlainText:
                snippet = snippet.replace('$', '\\$')
            completion = sublime.CompletionItem.snippet_completion(
                trigger=st_trigger,
                snippet=snippet,
                annotation=st_annotation,
                kind=kind,
                details=st_details)

        return completion

    def handle_response(self, response: Optional[Union[dict, List]], completion_list: sublime.CompletionList,
                        can_resolve_completion_items: bool) -> None:
        response_items = []  # type: List[Dict]
        flags = 0
        if settings.only_show_lsp_completions:
            flags |= sublime.INHIBIT_WORD_COMPLETIONS
            flags |= sublime.INHIBIT_EXPLICIT_COMPLETIONS
            flags |= sublime.INHIBIT_REORDER
        if isinstance(response, dict):
            response_items = response["items"] or []
            if response.get("isIncomplete", False):
                flags |= sublime.DYNAMIC_COMPLETIONS
        elif isinstance(response, list):
            response_items = response
        response_items = sorted(response_items, key=lambda item: item.get("sortText") or item["label"])
        CompletionHandler.completions = response_items
        items = [self.format_completion(response_item, index, can_resolve_completion_items)
                 for index, response_item in enumerate(response_items)]
        resolve(completion_list, items, flags)

    def handle_error(self, error: dict, completion_list: sublime.CompletionList) -> None:
        resolve(completion_list, [])
        CompletionHandler.completions = []
        sublime.status_message('Completion error: ' + str(error.get('message')))
