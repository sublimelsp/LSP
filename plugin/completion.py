from __future__ import annotations
from .core.constants import COMPLETION_KINDS
from .core.edit import apply_text_edits
from .core.logging import debug
from .core.promise import Promise
from .core.protocol import EditRangeWithInsertReplace
from .core.protocol import CompletionItem
from .core.protocol import CompletionItemDefaults
from .core.protocol import CompletionItemKind
from .core.protocol import CompletionItemTag
from .core.protocol import CompletionList
from .core.protocol import CompletionParams
from .core.protocol import Error
from .core.protocol import InsertReplaceEdit
from .core.protocol import InsertTextFormat
from .core.protocol import MarkupContent, MarkedString, MarkupKind
from .core.protocol import Range
from .core.protocol import Request
from .core.protocol import TextEdit
from .core.registry import LspTextCommand
from .core.sessions import Session
from .core.settings import userprefs
from .core.views import FORMAT_STRING, FORMAT_MARKUP_CONTENT
from .core.views import MarkdownLangMap
from .core.views import minihtml
from .core.views import range_to_region
from .core.views import show_lsp_popup
from .core.views import text_document_position_params
from .core.views import update_lsp_popup
from typing import Any, Callable, Generator, List, Tuple, Union
from typing import cast
from typing_extensions import TypeAlias, TypeGuard
import functools
import html
import sublime
import weakref
import webbrowser

SessionName: TypeAlias = str
CompletionResponse: TypeAlias = Union[List[CompletionItem], CompletionList, None]
ResolvedCompletions: TypeAlias = Tuple[Union[CompletionResponse, Error], 'weakref.ref[Session]']
CompletionsStore: TypeAlias = Tuple[List[CompletionItem], CompletionItemDefaults]


def format_completion(
    item: CompletionItem,
    index: int,
    can_resolve_completion_items: bool,
    session_name: str,
    item_defaults: CompletionItemDefaults,
    view_id: int
) -> sublime.CompletionItem:
    # This is a hot function. Don't do heavy computations or IO in this function.
    lsp_label = item['label']
    lsp_label_details = item.get('labelDetails') or {}
    lsp_label_detail = lsp_label_details.get('detail') or ""
    lsp_label_description = lsp_label_details.get('description') or ""
    lsp_filter_text = item.get('filterText') or ""
    lsp_detail = (item.get('detail') or "").replace("\n", " ")
    completion_kind = item.get('kind')
    kind = COMPLETION_KINDS.get(completion_kind, sublime.KIND_AMBIGUOUS) if completion_kind else sublime.KIND_AMBIGUOUS
    details: list[str] = []
    if can_resolve_completion_items or item.get('documentation'):
        # Not using "make_command_link" in a hot path to avoid slow json.dumps.
        args = '{{"view_id":{},"command":"lsp_resolve_docs","args":{{"index":{},"session_name":"{}"}}}}'.format(
            view_id, index, session_name)
        href = f'subl:lsp_run_text_command_helper {args}'
        details.append(f"<a href='{href}'>More</a>")
    if lsp_label_detail and (lsp_label + lsp_label_detail).startswith(lsp_filter_text):
        if lsp_label_detail[0].isalnum() and lsp_label.startswith(lsp_filter_text):
            # labelDetails.detail is likely a type annotation
            # Don't append it to the trigger: https://github.com/sublimelsp/LSP/issues/2169
            trigger = lsp_label
            details.append(html.escape(lsp_label_detail))
        else:
            # labelDetails.detail is likely a function signature
            trigger = lsp_label + lsp_label_detail
        annotation = lsp_label_description or lsp_detail
    else:
        if lsp_label.startswith(lsp_filter_text):
            trigger = lsp_label
            if lsp_label_detail:
                details.append(html.escape(lsp_label + lsp_label_detail))
        else:
            trigger = lsp_filter_text
            details.append(html.escape(lsp_label + lsp_label_detail))
        if lsp_label_description:
            annotation = lsp_label_description
            if lsp_detail:
                details.append(html.escape(lsp_detail))
        else:
            annotation = lsp_detail
    if item.get('deprecated') or CompletionItemTag.Deprecated in item.get('tags', []):
        annotation = "DEPRECATED - " + annotation if annotation else "DEPRECATED"
    text_edit = item.get('textEdit', item_defaults.get('editRange'))
    if text_edit and 'insert' in text_edit and 'replace' in text_edit:
        insert_mode = userprefs().completion_insert_mode
        oposite_insert_mode = 'Replace' if insert_mode == 'insert' else 'Insert'
        command_url = "subl:lsp_commit_completion_with_opposite_insert_mode"
        details.append(f"<a href='{command_url}'>{oposite_insert_mode}</a>")
    completion = sublime.CompletionItem(
        trigger,
        annotation,
        # Not using "sublime.format_command" in a hot path to avoid slow json.dumps.
        f'lsp_select_completion {{"index":{index},"session_name":"{session_name}"}}',
        sublime.CompletionFormat.COMMAND,
        kind,
        details=" | ".join(details)
    )
    if text_edit:
        completion.flags = sublime.COMPLETION_FLAG_KEEP_PREFIX
    return completion


def get_text_edit_range(text_edit: TextEdit | InsertReplaceEdit) -> Range:
    if 'insert' in text_edit and 'replace' in text_edit:
        text_edit = cast(InsertReplaceEdit, text_edit)
        insert_mode = userprefs().completion_insert_mode
        if LspCommitCompletionWithOppositeInsertMode.active:
            insert_mode = 'replace' if insert_mode == 'insert' else 'insert'
        return text_edit.get(insert_mode)  # type: ignore
    text_edit = cast(TextEdit, text_edit)
    return text_edit['range']


def is_range(val: Any) -> TypeGuard[Range]:
    return isinstance(val, dict) and 'start' in val and 'end' in val


def is_edit_range(val: Any) -> TypeGuard[EditRangeWithInsertReplace]:
    return isinstance(val, dict) and 'insert' in val and 'replace' in val


def completion_with_defaults(item: CompletionItem, item_defaults: CompletionItemDefaults) -> CompletionItem:
    """ Currently supports defaults for: ["editRange", "insertTextFormat", "data"] """
    if not item_defaults:
        return item
    default_text_edit: TextEdit | InsertReplaceEdit | None = None
    edit_range = item_defaults.get('editRange')
    if edit_range:
        #  If textEditText is not provided and a list's default range is provided
        # the label property is used as a text.
        new_text = item.get('textEditText') or item['label']
        if is_edit_range(edit_range):
            default_text_edit = {
                'newText': new_text,
                'insert': edit_range.get('insert'),
                'replace': edit_range.get('insert'),
            }
        elif is_range(edit_range):
            default_text_edit = {
                'newText': new_text,
                'range': edit_range
            }
    if default_text_edit and 'textEdit' not in item:
        item['textEdit'] = default_text_edit
    default_insert_text_format = item_defaults.get('insertTextFormat')
    if default_insert_text_format and 'insertTextFormat' not in item:
        item['insertTextFormat'] = default_insert_text_format
    default_data = item_defaults.get('data')
    if default_data and 'data' not in item:
        item['data'] = default_data
    return item


class QueryCompletionsTask:
    """
    Represents pending completion requests.

    Can be canceled while in progress in which case the "on_done_async" callback will get immediately called with empty
    list and the pending response from the server(s) will be canceled and results ignored.

    All public methods must only be called on the async thread and the "on_done_async" callback will also be called
    on the async thread.
    """
    def __init__(
        self,
        view: sublime.View,
        location: int,
        triggered_manually: bool,
        on_done_async: Callable[[list[sublime.CompletionItem], sublime.AutoCompleteFlags], None]
    ) -> None:
        self._view = view
        self._location = location
        self._triggered_manually = triggered_manually
        self._on_done_async = on_done_async
        self._resolved = False
        self._pending_completion_requests: dict[int, weakref.ref[Session]] = {}

    def query_completions_async(self, sessions: list[Session]) -> None:
        promises = [self._create_completion_request_async(session) for session in sessions]
        Promise.all(promises).then(lambda response: self._resolve_completions_async(response))

    def _create_completion_request_async(self, session: Session) -> Promise[ResolvedCompletions]:
        params = cast(CompletionParams, text_document_position_params(self._view, self._location))
        request = Request.complete(params, self._view)
        promise, request_id = session.send_request_task_2(request)
        weak_session = weakref.ref(session)
        self._pending_completion_requests[request_id] = weak_session
        return promise.then(lambda response: self._on_completion_response_async(response, request_id, weak_session))

    def _on_completion_response_async(
        self, response: CompletionResponse, request_id: int, weak_session: weakref.ref[Session]
    ) -> ResolvedCompletions:
        self._pending_completion_requests.pop(request_id, None)
        return (response, weak_session)

    def _resolve_completions_async(self, responses: list[ResolvedCompletions]) -> None:
        if self._resolved:
            return
        LspSelectCompletionCommand.completions = {}
        items: list[sublime.CompletionItem] = []
        item_defaults: CompletionItemDefaults = {}
        errors: list[Error] = []
        flags = sublime.AutoCompleteFlags.NONE
        prefs = userprefs()
        if prefs.inhibit_snippet_completions:
            flags |= sublime.AutoCompleteFlags.INHIBIT_EXPLICIT_COMPLETIONS
        if prefs.inhibit_word_completions:
            flags |= sublime.AutoCompleteFlags.INHIBIT_WORD_COMPLETIONS
        view_settings = self._view.settings()
        include_snippets = view_settings.get("auto_complete_include_snippets") and \
            (self._triggered_manually or view_settings.get("auto_complete_include_snippets_when_typing"))
        for response, weak_session in responses:
            if isinstance(response, Error):
                errors.append(response)
                continue
            session = weak_session()
            if not session:
                continue
            response_items: list[CompletionItem] = []
            if isinstance(response, dict):
                response_items = response["items"] or []
                item_defaults = response.get('itemDefaults') or {}
                if response.get("isIncomplete", False):
                    flags |= sublime.AutoCompleteFlags.DYNAMIC_COMPLETIONS
            elif isinstance(response, list):
                response_items = response
            response_items = sorted(response_items, key=lambda item: item.get("sortText") or item["label"])
            LspSelectCompletionCommand.completions[session.config.name] = response_items, item_defaults
            can_resolve_completion_items = session.has_capability('completionProvider.resolveProvider')
            config_name = session.config.name
            items.extend(
                format_completion(
                    response_item, index, can_resolve_completion_items, config_name, item_defaults, self._view.id())
                for index, response_item in enumerate(response_items)
                if include_snippets or response_item.get("kind") != CompletionItemKind.Snippet)
        if items:
            flags |= sublime.AutoCompleteFlags.INHIBIT_REORDER
        if errors:
            error_messages = ", ".join(str(error) for error in errors)
            sublime.status_message(f'Completion error: {error_messages}')
        self._resolve_task_async(items, flags)

    def cancel_async(self) -> None:
        self._resolve_task_async([])
        self._cancel_pending_requests_async()

    def _cancel_pending_requests_async(self) -> None:
        for request_id, weak_session in self._pending_completion_requests.items():
            session = weak_session()
            if session:
                session.cancel_request(request_id, False)
        self._pending_completion_requests.clear()

    def _resolve_task_async(
        self,
        completions: list[sublime.CompletionItem],
        flags: sublime.AutoCompleteFlags = sublime.AutoCompleteFlags.NONE
    ) -> None:
        if not self._resolved:
            self._resolved = True
            self._on_done_async(completions, flags)


class LspResolveDocsCommand(LspTextCommand):

    def run(self, edit: sublime.Edit, index: int, session_name: str, event: dict | None = None) -> None:

        def run_async() -> None:
            items, item_defaults = LspSelectCompletionCommand.completions[session_name]
            item = completion_with_defaults(items[index], item_defaults)
            session = self.session_by_name(session_name, 'completionProvider.resolveProvider')
            if session:
                request = Request.resolveCompletionItem(item, self.view)
                language_map = session.markdown_language_id_to_st_syntax_map()
                handler = functools.partial(self._handle_resolve_response_async, language_map)
                session.send_request_async(request, handler)
            else:
                self._handle_resolve_response_async(None, item)

        sublime.set_timeout_async(run_async)

    def _handle_resolve_response_async(self, language_map: MarkdownLangMap | None, item: CompletionItem) -> None:
        detail = ""
        documentation = ""
        if item:
            detail = self._format_documentation(item.get('detail') or "", language_map)
            documentation = self._format_documentation(item.get("documentation") or "", language_map)
        if not documentation:
            markdown: MarkupContent = {"kind": MarkupKind.Markdown, "value": "*No documentation available.*"}
            # No need for a language map here
            documentation = self._format_documentation(markdown, None)
        minihtml_content = ""
        if detail:
            minihtml_content += f"<div class='highlight'>{detail}</div>"
        if documentation:
            minihtml_content += documentation

        def run_main() -> None:
            if not self.view.is_valid():
                return
            if self.view.is_popup_visible():
                update_lsp_popup(self.view, minihtml_content, md=False)
            else:
                show_lsp_popup(
                    self.view,
                    minihtml_content,
                    flags=sublime.PopupFlags.COOPERATE_WITH_AUTO_COMPLETE,
                    md=False,
                    on_navigate=self._on_navigate)

        sublime.set_timeout(run_main)

    def _format_documentation(
        self,
        content: MarkedString | MarkupContent,
        language_map: MarkdownLangMap | None
    ) -> str:
        return minihtml(self.view, content, FORMAT_STRING | FORMAT_MARKUP_CONTENT, language_map)

    def _on_navigate(self, url: str) -> None:
        webbrowser.open(url)


class LspCommitCompletionWithOppositeInsertMode(LspTextCommand):
    active = False

    def run(self, edit: sublime.Edit, event: dict | None = None) -> None:
        LspCommitCompletionWithOppositeInsertMode.active = True
        self.view.run_command("commit_completion")
        LspCommitCompletionWithOppositeInsertMode.active = False


class LspSelectCompletionCommand(LspTextCommand):

    completions: dict[SessionName, CompletionsStore] = {}

    def run(self, edit: sublime.Edit, index: int, session_name: str) -> None:
        items, item_defaults = LspSelectCompletionCommand.completions[session_name]
        item = completion_with_defaults(items[index], item_defaults)
        text_edit = item.get("textEdit")
        if text_edit:
            new_text = text_edit["newText"].replace("\r", "")
            edit_region = range_to_region(get_text_edit_range(text_edit), self.view)
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

    def want_event(self) -> bool:
        return False

    def _on_resolved_async(self, session_name: str, item: CompletionItem) -> None:
        sublime.set_timeout(functools.partial(self._on_resolved, session_name, item))

    def _on_resolved(self, session_name: str, item: CompletionItem) -> None:
        additional_edits = item.get('additionalTextEdits')
        if additional_edits:
            apply_text_edits(self.view, additional_edits)
        command = item.get("command")
        if command:
            debug(f'Running server command "{command}" for view {self.view.id()}')
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
