import html
import mdpopups
import sublime
import sublime_plugin
import webbrowser
from .core.edit import parse_text_edit
from .core.protocol import Request, InsertTextFormat, Range, CompletionItemTag
from .core.registry import session_for_view, LSPViewEventListener
from .core.settings import settings
from .core.typing import Any, List, Dict, Optional, Union, Generator
from .core.views import COMPLETION_KINDS
from .core.views import FORMAT_STRING, FORMAT_MARKUP_CONTENT, minihtml
from .core.views import text_document_position_params, range_to_region


class LspResolveDocsCommand(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit, index: int) -> None:
        item = CompletionHandler.completions[index]
        detail = self.format_documentation(item.get('detail') or "")
        documentation = self.format_documentation(item.get("documentation") or "")

        # don't show the detail in the cooperate AC popup if it is already shown in the AC details filed.
        self.is_detail_shown = bool(detail)
        minihtml_content = self.get_content(documentation, detail)
        # NOTE: For some reason, ST does not like it when we show a popup from within this run method.
        sublime.set_timeout(lambda: self.show_popup(minihtml_content))

        if not detail or not documentation:
            # To make sure that the detail or documentation fields doesn't exist we need to resove the completion item.
            # If those fields appear after the item is resolved we show them in the popup.
            self.do_resolve(item)

    def format_documentation(self, content: str) -> str:
        return minihtml(self.view, content, allowed_formats=FORMAT_STRING | FORMAT_MARKUP_CONTENT)

    def get_content(self, documentation: str, detail: str) -> str:
        content = ""
        if detail and not self.is_detail_shown:
            content += "<div class='highlight' style='margin: 6px'>{}</div>".format(detail)
        if documentation:
            content += "<div style='margin: 6px'>{}</div>".format(documentation)
        return content

    def show_popup(self, minihtml_content: str) -> None:
        viewport_width = self.view.viewport_extent()[0]
        mdpopups.show_popup(
            self.view,
            minihtml_content,
            flags=sublime.COOPERATE_WITH_AUTO_COMPLETE,
            max_width=viewport_width,
            allow_code_wrap=True,
            on_navigate=self.on_navigate
        )

    def on_navigate(self, url: str) -> None:
        webbrowser.open(url)

    def do_resolve(self, item: dict) -> None:
        session = session_for_view(self.view, 'completionProvider.resolveProvider')
        if session:
            session.send_request(
                Request.resolveCompletionItem(item),
                lambda res: self.handle_resolve_response(res))

    def handle_resolve_response(self, item: Optional[dict]) -> None:
        if not item:
            return
        detail = self.format_documentation(item.get('detail') or "")
        documentation = self.format_documentation(item.get("documentation") or "")
        minihtml_content = self.get_content(documentation, detail)
        show = self.update_popup if self.view.is_popup_visible() else self.show_popup
        # NOTE: Update/show popups from the main thread, or else the popup might make the AC widget disappear.
        sublime.set_timeout(lambda: show(minihtml_content))

    def update_popup(self, minihtml_content: str) -> None:
        mdpopups.update_popup(self.view, minihtml_content)


class LspCompleteCommand(sublime_plugin.TextCommand):

    def epilogue(self, item: Dict[str, Any]) -> None:
        additional_edits = item.get('additionalTextEdits')
        if additional_edits:
            edits = [parse_text_edit(additional_edit) for additional_edit in additional_edits]
            self.view.run_command("lsp_apply_document_edit", {'changes': edits})
        command = item.get("command")
        if command:
            self.view.run_command("lsp_execute", {"command_name": command})


class LspCompleteInsertTextCommand(LspCompleteCommand):

    def run(self, edit: sublime.Edit, **item: Any) -> None:
        insert_text = item.get("insertText") or item["label"]
        if item.get("insertTextFormat", InsertTextFormat.PlainText) == InsertTextFormat.Snippet:
            self.view.run_command("insert_snippet", {"contents": insert_text})
        else:
            self.view.run_command("insert", {"characters": insert_text})
        self.epilogue(item)


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
        self.epilogue(item)

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


def is_deprecated(item: dict) -> bool:
    return item.get("deprecated", False) or CompletionItemTag.Deprecated in item.get("tags", [])


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
        return cls.has_supported_syntax(view_settings)

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
        self.purge_changes()
        completion_list = sublime.CompletionList()
        capability = session.get_capability('completionProvider') or {}
        can_resolve_completion_items = bool(capability.get('resolveProvider', False))
        session.send_request(
            Request.complete(text_document_position_params(self.view, locations[0])),
            lambda res: self.handle_response(res, completion_list, can_resolve_completion_items),
            lambda res: self.handle_error(res, completion_list))
        return completion_list

    def format_completion(self, item: dict, index: int, can_resolve_completion_items: bool) -> sublime.CompletionItem:
        # This is a hot function. Don't do heavy computations or IO in this function.
        item_kind = item.get("kind")
        if isinstance(item_kind, int) and 1 <= item_kind <= len(COMPLETION_KINDS):
            kind = COMPLETION_KINDS[item_kind - 1]
        else:
            kind = sublime.KIND_AMBIGUOUS

        if is_deprecated(item):
            kind = (kind[0], '⚠', "⚠ {} - Deprecated".format(kind[2]))

        lsp_label = item["label"]
        lsp_filter_text = item.get("filterText")
        lsp_detail = html.escape(item.get("detail") or "").replace('\n', ' ')

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
        elif item.get("additionalTextEdits") or item.get("command"):
            # It's an insertText, but additionalEdits or a command requires us to use a command completion.
            completion = sublime.CompletionItem.command_completion(
                trigger=st_trigger,
                command="lsp_complete_insert_text",
                args=item,
                annotation=st_annotation,
                kind=kind,
                details=st_details)
        else:
            # A plain old completion suffices for insertText with no additionalTextEdits and no command.
            if item.get("insertTextFormat", InsertTextFormat.PlainText) == InsertTextFormat.PlainText:
                st_format = sublime.COMPLETION_FORMAT_TEXT
            else:
                st_format = sublime.COMPLETION_FORMAT_SNIPPET
            completion = sublime.CompletionItem(
                trigger=st_trigger,
                annotation=st_annotation,
                completion=item.get("insertText") or item["label"],
                completion_format=st_format,
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
