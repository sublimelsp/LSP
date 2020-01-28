import sublime
import sublime_plugin

from .core.protocol import Request, Range, InsertTextFormat
from .core.settings import settings, client_configs
from .core.logging import debug
from .core.completion import parse_completion_response, format_completion
from .core.registry import session_for_view, client_from_session, LSPViewEventListener
from .core.configurations import is_supported_syntax
from .core.documents import get_document_position
from .core.sessions import Session
from .core.edit import parse_text_edit
from .core.views import range_to_region
from .core.typing import Any, List, Dict, Tuple, Optional, Union


last_text_command = None


class LspSelectCompletionItemCommand(sublime_plugin.TextCommand):
    def run(self, edit: 'Any', item: 'Dict') -> None:
        insert_text_format = item.get("insertTextFormat")

        text_edit = item.get('textEdit')
        if text_edit:
            new_text = text_edit.get('newText')

            range = Range.from_lsp(text_edit['range'])
            edit_region = range_to_region(range, self.view)

            if insert_text_format == InsertTextFormat.Snippet:
                self.view.run_command("insert_snippet", {"contents": new_text})
            else:
                # subtract the prefix from the end
                end_edit_position = edit_region.end() - len(CompletionHandler.prefix)
                edit_range = sublime.Region(edit_region.begin(), end_edit_position)
                self.view.replace(edit, edit_range, new_text)

                # move the cursor to the end of the text edit
                sel = self.view.sel()
                sel.clear()
                sel.add(edit_range.begin() + len(new_text))
        else:
            completion = item.get('insertText') or item.get('label') or ""
            current_point = self.view.sel()[0].begin()
            if insert_text_format == InsertTextFormat.Snippet:
                self.view.run_command("insert_snippet", {"contents": completion})
            else:
                self.view.insert(edit, current_point, completion)

        # import statements, etc. some servers only return these after a resolve.
        additional_edits = item.get('additionalTextEdits')
        if additional_edits:
            self.apply_additional_edits(additional_edits)

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

    def handle_resolve_response(self, response: 'Optional[Dict]') -> None:
        if response:
            additional_edits = response.get('additionalTextEdits')
            if additional_edits:
                self.apply_additional_edits(additional_edits)

    def apply_additional_edits(self, additional_edits: 'List[Dict]') -> None:
        edits = list(parse_text_edit(additional_edit) for additional_edit in additional_edits)
        debug('applying additional edits:', edits)
        self.view.run_command("lsp_apply_document_edit", {'changes': edits})
        sublime.status_message('Applied additional edits for completion')


class CompletionHelper(sublime_plugin.EventListener):
    def on_text_command(self, view: sublime.View, command_name: str, args: Optional[Any]) -> None:
        global last_text_command
        last_text_command = command_name


class LspTrimCompletionCommand(sublime_plugin.TextCommand):

    def run(self, edit: sublime.Edit, range: Optional[Tuple[int, int]] = None) -> None:
        if range:
            start, end = range
            region = sublime.Region(start, end)
            self.view.erase(edit, region)


class CompletionHandler(LSPViewEventListener):
    # the last known prefix
    prefix = ""

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.initialized = False
        self.enabled = False
        self.trigger_chars = []  # type: List[str]
        self.completion_list = sublime.CompletionList()
        self.last_location = -1
        self.committing = False
        self.response_items = []  # type: List[dict]

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

            self.trigger_chars = completionProvider.get(
                'triggerCharacters') or []
            if self.trigger_chars:
                self.register_trigger_chars(session)
            self.auto_complete_selector = self.view.settings().get("auto_complete_selector", "") or ""

    def _view_language(self, config_name: str) -> Optional[str]:
        languages = self.view.settings().get('lsp_language')
        return languages.get(config_name) if languages else None

    def register_trigger_chars(self, session: Session) -> None:
        completion_triggers = self.view.settings().get('auto_complete_triggers', []) or []  # type: List[Dict[str, str]]
        view_language = self._view_language(session.config.name)
        if view_language:
            for language in session.config.languages:
                if language.id == view_language:
                    for scope in language.scopes:
                        # debug("registering", self.trigger_chars, "for", scope)
                        scope_trigger = next(
                            (trigger for trigger in completion_triggers if trigger.get('selector', None) == scope),
                            None
                        )
                        if not scope_trigger:  # do not override user's trigger settings.
                            completion_triggers.append({
                                'characters': "".join(self.trigger_chars),
                                'selector': scope
                            })

            self.view.settings().set('auto_complete_triggers', completion_triggers)

    def on_query_completions(self, prefix: str, locations: 'List[int]') -> 'Optional[sublime.CompletionList]':
        CompletionHandler.prefix = prefix
        if not self.initialized:
            self.initialize()

        if not self.enabled:
            return None

        self.completion_list = sublime.CompletionList()
        self.last_location = locations[0]
        self.do_request(prefix, locations)

        return self.completion_list

    def on_text_command(self, command_name: str, args: 'Optional[Any]') -> None:
        self.committing = command_name in ('commit_completion', 'auto_complete')

    def do_request(self, prefix: str, locations: 'List[int]') -> None:
        # don't store client so we can handle restarts
        client = client_from_session(session_for_view(self.view, 'completionProvider', locations[0]))
        if not client:
            return

        self.manager.documents.purge_changes(self.view)
        document_position = get_document_position(self.view, locations[0])
        if document_position:
            client.send_request(
                Request.complete(document_position),
                self.handle_response,
                self.handle_error)

    def handle_response(self, response: 'Optional[Union[Dict,List]]') -> None:
        _last_row, last_col = self.view.rowcol(self.last_location)

        response_items, response_incomplete = parse_completion_response(response)
        self.response_items = response_items
        items = list(format_completion(item, last_col) for item in response_items)

        flags = 0
        if settings.only_show_lsp_completions:
            flags |= sublime.INHIBIT_WORD_COMPLETIONS
            flags |= sublime.INHIBIT_EXPLICIT_COMPLETIONS

        if response_incomplete:
            flags |= sublime.DYNAMIC_COMPLETIONS

        self.completion_list.set_completions(items, flags)

    def handle_error(self, error: dict) -> None:
        sublime.status_message('Completion error: ' + str(error.get('message')))

    def do_resolve(self, item: dict) -> None:
        client = client_from_session(session_for_view(self.view, 'completionProvider', self.last_location))
        if not client:
            return

        client.send_request(Request.resolveCompletionItem(item), self.handle_resolve_response)

    def handle_resolve_response(self, response: Optional[Dict]) -> None:
        if response:
            additional_edits = response.get('additionalTextEdits')
            if additional_edits:
                self.apply_additional_edits(additional_edits)

    def apply_additional_edits(self, additional_edits: List[Dict]) -> None:
        edits = list(parse_text_edit(additional_edit) for additional_edit in additional_edits)
        debug('applying additional edits:', edits)
        self.view.run_command("lsp_apply_document_edit", {'changes': edits})
        sublime.status_message('Applied additional edits for completion')
