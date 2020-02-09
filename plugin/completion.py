import sublime
import sublime_plugin

from .core.protocol import Request, Range, InsertTextFormat
from .core.settings import settings, client_configs
from .core.logging import debug
from .core.completion import parse_completion_response, format_completion
from .core.registry import session_for_view, client_from_session, LSPViewEventListener
from .core.configurations import is_supported_syntax
from .core.sessions import Session
from .core.edit import parse_text_edit
from .core.views import range_to_region
from .core.typing import Any, List, Dict, Tuple, Optional, Union
from .core.views import text_document_position_params


class LspSelectCompletionItemCommand(sublime_plugin.TextCommand):
    def run(self, edit: Any, item: dict) -> None:
        insert_text_format = item.get("insertTextFormat")

        text_edit = item.get('textEdit')
        if text_edit:
            # insert the removed command completion item prefix
            # so we don't have to calculate the offset for the textEdit range
            for sel in self.view.sel():
                self.view.insert(edit, sel.begin(), CompletionHandler.last_prefix)

            new_text = text_edit.get('newText')

            range = Range.from_lsp(text_edit['range'])
            edit_region = range_to_region(range, self.view)

            self.view.erase(edit, edit_region)
            if insert_text_format == InsertTextFormat.Snippet:
                self.view.run_command("insert_snippet", {"contents": new_text})
            else:
                self.view.insert(edit, edit_region.begin(), new_text)
        else:
            completion = item.get('insertText') or item.get('label') or ""
            if insert_text_format == InsertTextFormat.Snippet:
                self.view.run_command("insert_snippet", {"contents": completion})
            else:
                for sel in self.view.sel():
                    self.view.insert(edit, sel.begin(), completion)

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


class LspTrimCompletionCommand(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit, range: Optional[Tuple[int, int]] = None) -> None:
        if range:
            start, end = range
            region = sublime.Region(start, end)
            self.view.erase(edit, region)


class CompletionHandler(LSPViewEventListener):
    last_prefix = ""

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.initialized = False
        self.enabled = False
        self.test_completions = None  # type: List[dict]

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

    def _view_language(self, config_name: str) -> Optional[str]:
        languages = self.view.settings().get('lsp_language')
        return languages.get(config_name) if languages else None

    def register_trigger_chars(self, session: Session, trigger_chars: List[str]) -> None:
        completion_triggers = self.view.settings().get('auto_complete_triggers', []) or []  # type: List[Dict[str, str]]
        view_language = self._view_language(session.config.name)
        if view_language:
            for language in session.config.languages:
                if language.id == view_language:
                    for scope in language.scopes:
                        # debug("registering", trigger_chars, "for", scope)
                        scope_trigger = next(
                            (trigger for trigger in completion_triggers if trigger.get('selector', None) == scope),
                            None
                        )
                        if not scope_trigger:  # do not override user's trigger settings.
                            completion_triggers.append({
                                'characters': "".join(trigger_chars),
                                'selector': scope
                            })

            self.view.settings().set('auto_complete_triggers', completion_triggers)

    def on_query_completions(self, prefix: str, locations: List[int]) -> Optional[sublime.CompletionList]:
        if not self.initialized:
            self.initialize()

        if not self.enabled:
            return None

        completion_list = sublime.CompletionList()

        # this is for tests
        if self.test_completions:
            self.handle_response(self.test_completions, completion_list, prefix)
        else:
            self.do_request(completion_list, prefix, locations)

        return completion_list

    def do_request(self, completion_list: sublime.CompletionList, prefix: str, locations: List[int]) -> None:
        # don't store client so we can handle restarts
        client = client_from_session(session_for_view(self.view, 'completionProvider', locations[0]))
        if not client:
            return

        self.manager.documents.purge_changes(self.view)
        document_position = text_document_position_params(self.view, locations[0])
        client.send_request(
            Request.complete(document_position),
            lambda res: self.handle_response(res, completion_list, prefix),
            self.handle_error)

    def handle_response(self, response: Optional[Union[dict, List]],
                        completion_list: sublime.CompletionList, prefix: str) -> None:
        response_items, response_incomplete = parse_completion_response(response)
        items = list(format_completion(item) for item in response_items)

        flags = 0
        if settings.only_show_lsp_completions:
            flags |= sublime.INHIBIT_WORD_COMPLETIONS
            flags |= sublime.INHIBIT_EXPLICIT_COMPLETIONS

        if response_incomplete:
            flags |= sublime.DYNAMIC_COMPLETIONS

        completion_list.set_completions(items, flags)
        CompletionHandler.last_prefix = prefix

    def handle_error(self, error: dict) -> None:
        sublime.status_message('Completion error: ' + str(error.get('message')))
