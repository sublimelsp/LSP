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
from .core.restore_lines import RestoreLines


class LspSelectCompletionItemCommand(sublime_plugin.TextCommand):
    def run(self, edit: Any, item: Any, restore_lines_dict: dict) -> None:
        insert_text_format = item.get("insertTextFormat")

        text_edit = item.get('textEdit')
        if text_edit:
            # restore the lines
            # so we don't have to calculate the offset for the textEdit range
            restore_lines = RestoreLines.from_dict(restore_lines_dict)
            restore_lines.restore_lines(edit, self.view)

            new_text = text_edit.get('newText')

            range = Range.from_lsp(text_edit['range'])
            edit_region = range_to_region(range, self.view)

            # calculate offset by comparing cursor position with edit_region.begin.
            # by applying the offset to all selections
            # the TextEdit becomes valid for all selections 
            cursor = self.view.sel()[0].begin()  # type: int

            offset_start = cursor - edit_region.begin()
            offset_length = edit_region.end() - edit_region.begin()

            # erease regions from bottom to top
            for sel in reversed(self.view.sel()):
                begin = sel.begin() - offset_start
                end = begin + offset_length
                r = sublime.Region(begin, end)
                self.view.erase(edit, r)

            if insert_text_format == InsertTextFormat.Snippet:
                self.view.run_command("insert_snippet", {"contents": new_text})
            else:
                # insert text from bottom to top
                for sel in reversed(self.view.sel()):
                    self.view.insert(edit, sel.begin(), new_text)
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


class LspTrimCompletionCommand(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit, range: Optional[Tuple[int, int]] = None) -> None:
        if range:
            start, end = range
            region = sublime.Region(start, end)
            self.view.erase(edit, region)


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

        self.do_request(completion_list, locations)

        return completion_list

    def do_request(self, completion_list: sublime.CompletionList, locations: List[int]) -> None:
        # don't store client so we can handle restarts
        client = client_from_session(session_for_view(self.view, 'completionProvider', locations[0]))
        if not client:
            return

        # save lines to restore them later (only when selecting a completion item with a TextEdit)
        restore_lines = RestoreLines()
        restore_lines.save_lines(locations, self.view)

        self.manager.documents.purge_changes(self.view)
        document_position = text_document_position_params(self.view, locations[0])
        client.send_request(
            Request.complete(document_position),
            lambda res: self.handle_response(res, completion_list, restore_lines),
            lambda res: self.handle_error(res, completion_list))

    def handle_response(self, response: Optional[Union[dict, List]],
                        completion_list: sublime.CompletionList, restore_lines: RestoreLines) -> None:
        response_items, response_incomplete = parse_completion_response(response)
        items = list(format_completion(item, restore_lines) for item in response_items)

        flags = 0
        if settings.only_show_lsp_completions:
            flags |= sublime.INHIBIT_WORD_COMPLETIONS
            flags |= sublime.INHIBIT_EXPLICIT_COMPLETIONS

        if response_incomplete:
            flags |= sublime.DYNAMIC_COMPLETIONS
        completion_list.set_completions(items, flags)

    def handle_error(self, error: dict, completion_list: sublime.CompletionList) -> None:
        completion_list.set_completions([])
        sublime.status_message('Completion error: ' + str(error.get('message')))
