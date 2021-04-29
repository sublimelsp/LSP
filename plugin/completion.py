import sublime
import sublime_plugin
import webbrowser
from .core.logging import debug
from .core.edit import parse_text_edit
from .core.protocol import Request, InsertTextFormat, Range, CompletionItem
from .core.registry import LspTextCommand
from .core.typing import Any, List, Dict, Optional, Generator, Union
from .core.views import FORMAT_STRING, FORMAT_MARKUP_CONTENT, minihtml
from .core.views import range_to_region
from .core.views import show_lsp_popup
from .core.views import update_lsp_popup

SessionName = str


class LspResolveDocsCommand(LspTextCommand):

    completions = {}  # type: Dict[SessionName, List[CompletionItem]]

    def run(self, edit: sublime.Edit, index: int, session_name: str, event: Optional[dict] = None) -> None:

        def run_async() -> None:
            item = self.completions[session_name][index]
            session = self.session_by_name(session_name, 'completionProvider.resolveProvider')
            if session:
                request = Request.resolveCompletionItem(item, self.view)
                session.send_request_async(request, self._handle_resolve_response_async)
            else:
                self._handle_resolve_response_async(item)

        sublime.set_timeout_async(run_async)

    def _format_documentation(self, content: Union[str, Dict[str, str]]) -> str:
        return minihtml(self.view, content, allowed_formats=FORMAT_STRING | FORMAT_MARKUP_CONTENT)

    def _handle_resolve_response_async(self, item: CompletionItem) -> None:
        detail = ""
        documentation = ""
        if item:
            detail = self._format_documentation(item.get('detail') or "")
            documentation = self._format_documentation(item.get("documentation") or "")
        if not documentation:
            documentation = self._format_documentation({"kind": "markdown", "value": "*No documentation available.*"})
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


class LspSelectCompletionItemCommand(LspTextCommand):
    def run(self, edit: sublime.Edit, item: CompletionItem, session_name: str) -> None:
        text_edit = item.get("textEdit")
        if text_edit:
            new_text = text_edit["newText"]
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
        else:
            insert_text = item.get("insertText") or item.get("label")
            if item.get("insertTextFormat", InsertTextFormat.PlainText) == InsertTextFormat.Snippet:
                self.view.run_command("insert_snippet", {"contents": insert_text})
            else:
                self.view.run_command("insert", {"characters": insert_text})
        self.epilogue(item, session_name)

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

    def epilogue(self, item: CompletionItem, session_name: str) -> None:
        session = self.session_by_name(session_name, 'completionProvider.resolveProvider')
        if session:
            request = Request.resolveCompletionItem(item, self.view)
            session.send_request_async(request, lambda response: self.on_resolved(response, session_name))
        else:
            self.on_resolved(item, session_name)

    def on_resolved(self, item: CompletionItem, session_name: str) -> None:
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
