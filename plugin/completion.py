from .core.edit import parse_text_edit
from .core.logging import debug
from .core.protocol import InsertReplaceEdit, TextEdit, RangeLsp, Request, InsertTextFormat, Range, CompletionItem
from .core.registry import LspTextCommand
from .core.settings import userprefs
from .core.typing import List, Dict, Optional, Generator, Union
from .core.views import FORMAT_STRING, FORMAT_MARKUP_CONTENT
from .core.views import MarkdownLangMap
from .core.views import minihtml
from .core.views import range_to_region
from .core.views import show_lsp_popup
from .core.views import update_lsp_popup
import functools
import sublime
import webbrowser

SessionName = str


def get_text_edit_range(text_edit: Union[TextEdit, InsertReplaceEdit]) -> RangeLsp:
    if 'insert' in text_edit and 'replace' in text_edit:
        text_edit = cast(InsertReplaceEdit, text_edit)
        insert_mode = userprefs().completion_insert_mode
        if LspCommitCompletionWithOppositeInsertMode.shift_pressed: # if shift is pressed, we want the oposite insert mode range
            insert_mode = 'replace' if insert_mode == 'insert' else 'insert'
        return text_edit.get(insert_mode, 'insert')
    return text_edit['range']


class LspResolveDocsCommand(LspTextCommand):

    completions = {}  # type: Dict[SessionName, List[CompletionItem]]

    def run(self, edit: sublime.Edit, index: int, session_name: str, event: Optional[dict] = None) -> None:

        def run_async() -> None:
            item = self.completions[session_name][index]
            session = self.session_by_name(session_name, 'completionProvider.resolveProvider')
            if session:
                request = Request.resolveCompletionItem(item, self.view)
                language_map = session.markdown_language_id_to_st_syntax_map()
                handler = functools.partial(self._handle_resolve_response_async, language_map)
                session.send_request_async(request, handler)
            else:
                self._handle_resolve_response_async(None, item)

        sublime.set_timeout_async(run_async)

    def _format_documentation(
        self,
        content: Union[str, Dict[str, str]],
        language_map: Optional[MarkdownLangMap]
    ) -> str:
        return minihtml(self.view, content, FORMAT_STRING | FORMAT_MARKUP_CONTENT, language_map)

    def _handle_resolve_response_async(self, language_map: Optional[MarkdownLangMap], item: CompletionItem) -> None:
        detail = ""
        documentation = ""
        if item:
            detail = self._format_documentation(item.get('detail') or "", language_map)
            documentation = self._format_documentation(item.get("documentation") or "", language_map)
        if not documentation:
            markdown = {"kind": "markdown", "value": "*No documentation available.*"}
            # No need for a language map here
            documentation = self._format_documentation(markdown, None)
        minihtml_content = ""
        if detail:
            minihtml_content += "<div class='highlight'>{}</div>".format(detail)
        if documentation:
            minihtml_content += documentation

        def run_main() -> None:
            if not self.view.is_valid():
                return
            if self.view.is_popup_visible():
                update_lsp_popup(self.view, minihtml_content, md=True)
            else:
                show_lsp_popup(
                    self.view,
                    minihtml_content,
                    flags=sublime.COOPERATE_WITH_AUTO_COMPLETE,
                    md=True,
                    on_navigate=self._on_navigate)

        sublime.set_timeout(run_main)

    def _on_navigate(self, url: str) -> None:
        webbrowser.open(url)


class LspCommitCompletionWithOppositeInsertMode(LspTextCommand):
    shift_pressed = False

    def run(self, edit: sublime.Edit) -> None:
        LspCommitCompletionWithOppositeInsertMode.shift_pressed = True
        self.view.run_command("commit_completion")
        LspCommitCompletionWithOppositeInsertMode.shift_pressed = False



class LspSelectCompletionItemCommand(LspTextCommand):
    def run(self, edit: sublime.Edit, item: CompletionItem, session_name: str) -> None:
        text_edit = item.get("textEdit")
        if text_edit:
            # resolve this
            # new_text = text_edit["newText"]
            # edit_region = range_to_region(Range.from_lsp(get_text_edit_range(text_edit)), self.view)
            # if item.get("insertTextFormat", InsertTextFormat.PlainText) == InsertTextFormat.Snippet:
            #     for region in self.translated_regions(edit_region):
            #         self.view.erase(edit, region)
            #     self.view.run_command("insert_snippet", {"contents": new_text})
            # else:
            #     for region in self.translated_regions(edit_region):
            #         # NOTE: Cannot do .replace, because ST will select the replacement.
            #         self.view.erase(edit, region)
            #         self.view.insert(edit, region.a, new_text)

            new_text = text_edit["newText"].replace("\r", "")
            edit_region = range_to_region(Range.from_lsp(text_edit['range']), self.view)
            for region in self._translated_regions(edit_region):
                self.view.erase(edit, region)
        else:
            new_text = item.get("insertText") or item["label"]
            new_text = new_text.replace("\r", "")
        if item.get("insertTextFormat", InsertTextFormat.PlainText) == InsertTextFormat.Snippet:
            self.view.run_command("insert_snippet", {"contents": new_text})
        else:
            self.view.run_command("insert", {"characters": new_text})
        # todo: this should all run from the worker thread
        session = self.session_by_name(session_name, 'completionProvider.resolveProvider')
        additional_text_edits = item.get('additionalTextEdits')
        if session and not additional_text_edits:
            session.send_request_async(
                Request.resolveCompletionItem(item, self.view),
                functools.partial(self._on_resolved_async, session_name))
        else:
            self._on_resolved(session_name, item)

    def _on_resolved_async(self, session_name: str, item: CompletionItem) -> None:
        sublime.set_timeout(functools.partial(self._on_resolved, session_name, item))

    def _on_resolved(self, session_name: str, item: CompletionItem) -> None:
        additional_edits = item.get('additionalTextEdits')
        if additional_edits:
            edits = [parse_text_edit(additional_edit) for additional_edit in additional_edits]
            self.view.run_command("lsp_apply_document_edit", {'changes': edits})
        command = item.get("command")
        if command:
            debug('Running server command "{}" for view {}'.format(command, self.view.id()))
            args = {
                "command_name": command["command"],
                "command_args": command.get("arguments"),
                "session_name": session_name
            }
            self.view.run_command("lsp_execute", args)

    def _translated_regions(self, edit_region: sublime.Region) -> Generator[sublime.Region, None, None]:
        selection = self.view.sel()
        primary_cursor_position = selection[0].b
        for region in reversed(selection):
            # For each selection region, apply the same removal as for the "primary" region.
            # To do that, translate, or offset, the LSP edit region into the non-"primary" regions.
            # The concept of "primary" is our own, and there is no mention of it in the LSP spec.
            translation = region.b - primary_cursor_position
            translated_edit_region = sublime.Region(edit_region.a + translation, edit_region.b + translation)
            yield translated_edit_region
