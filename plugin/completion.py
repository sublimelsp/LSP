import sublime
import sublime_plugin

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional, Union
    assert Any and List and Dict and Tuple and Callable and Optional and Union
except ImportError:
    pass

from .core.protocol import Request
from .core.settings import settings, client_configs
from .core.logging import debug
from .core.completion import parse_completion_response, format_completion
from .core.registry import session_for_view, client_from_session, LSPViewEventListener
from .core.configurations import is_supported_syntax
from .core.documents import get_document_position, position_is_word
from .core.sessions import Session
from .core.edit import parse_text_edit


last_text_command = None


class CompletionHelper(sublime_plugin.EventListener):
    def on_text_command(self, view: sublime.View, command_name: str, args: 'Optional[Any]') -> None:
        global last_text_command
        last_text_command = command_name


class LspTrimCompletionCommand(sublime_plugin.TextCommand):

    def run(self, edit: sublime.Edit, range: 'Optional[Tuple[int, int]]' = None) -> None:
        if range:
            start, end = range
            region = sublime.Region(start, end)
            self.view.erase(edit, region)


class CompletionHandler(LSPViewEventListener):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.initialized = False
        self.enabled = False
        self.trigger_chars = []  # type: List[str]
        self.resolve = False
        self.is_request_pending = False
        self.completions = []  # type: List[Any]
        self.last_prefix = ""
        self.last_location = -1
        self.committing = False
        self.response_items = []  # type: List[dict]
        self.response_incomplete = False

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
            self.resolve = completionProvider.get('resolveProvider') or False
            self.trigger_chars = completionProvider.get('triggerCharacters') or []
            if self.trigger_chars:
                self.register_trigger_chars(session)

    def _view_language(self, config_name: str) -> 'Optional[str]':
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

    def find_completion_item(self, inserted: str) -> 'Optional[dict]':
        """

        Returns the completionItem for a given replacement string.
        Matches exactly or up to first snippet placeholder ($s)

        """
        # TODO: candidate for extracting and thorough testing.
        if self.completions:
            for index, item in enumerate(self.completions):
                trigger, replacement = item

                snippet_offset = replacement.find('$', 2)
                if snippet_offset > -1:
                    if inserted.startswith(replacement[:snippet_offset]):
                        return self.response_items[index]
                else:
                    if replacement == inserted:
                        return self.response_items[index]
        return None

    def on_modified(self) -> None:
        # hide completion when backspacing past last completion.
        if self.view.sel()[0].begin() < self.last_location:
            self.last_location = -1
            self.view.run_command("hide_auto_complete")

        if self.committing:
            self.committing = False
            self.on_completion_inserted()
        else:
            if self.response_incomplete:
                self.update_completions()

    def on_completion_inserted(self) -> None:
        # get text inserted from last completion
        begin = self.last_location

        if begin < 0:
            return

        if position_is_word(self.view, begin):
            word = self.view.word(self.last_location)
            begin = word.begin()

        region = sublime.Region(begin, self.view.sel()[0].end())
        inserted = self.view.substr(region)

        item = self.find_completion_item(inserted)
        if not item:
            # issues 714 and 720 - calling view.word() on last_location includes a trigger char that is not part of
            # inserted completion.
            debug('No match for inserted "{}", skipping first char'.format(inserted))
            begin += 1
            item = self.find_completion_item(inserted[1:])

        if item:
            # the newText is already inserted, now we need to check where it should start.
            edit = item.get('textEdit')
            if edit:
                parsed_edit = parse_text_edit(edit)
                start, end, newText = parsed_edit
                edit_start_loc = self.view.text_point(*start)

                # if the edit started before the word, we need to trim back to the start of the edit.
                if edit_start_loc < begin:
                    trim_range = (edit_start_loc, begin)
                    debug('trimming between', trim_range, 'because textEdit', parsed_edit)
                    self.view.run_command("lsp_trim_completion", {'range': trim_range})

            # import statements, etc. some servers only return these after a resolve.
            additional_edits = item.get('additionalTextEdits')
            if additional_edits:
                self.apply_additional_edits(additional_edits)
            elif self.resolve:
                self.do_resolve(item)

        else:
            debug('could not find completion item for inserted "{}"'.format(inserted))

    def on_query_completions(self, prefix: str, locations: 'List[int]') -> 'Optional[Tuple[List[Tuple[str,str]], int]]':
        if not self.initialized:
            self.initialize()

        flags = 0
        if settings.only_show_lsp_completions:
            flags = sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS

        if not self.enabled:
            return None

        if self.last_location != locations[0]:
            self.last_prefix = prefix
            self.last_location = locations[0]
            self.do_request(prefix, locations)

        return (self.completions, flags)

    def on_text_command(self, command_name: str, args: 'Optional[Any]') -> None:
        self.committing = command_name in ('commit_completion', 'auto_complete')

    def do_request(self, prefix: str, locations: 'List[int]') -> None:
        if self.is_request_pending:
            return

        # don't store client so we can handle restarts
        client = client_from_session(session_for_view(self.view, 'completionProvider', locations[0]))
        if not client:
            return

        self.manager.documents.purge_changes(self.view)
        document_position = get_document_position(self.view, locations[0])
        if document_position:
            self.is_request_pending = True
            self.completions = []
            client.send_request(
                Request.complete(document_position),
                self.handle_response,
                self.handle_error)

    def do_resolve(self, item: dict) -> None:
        client = client_from_session(session_for_view(self.view, 'completionProvider', self.last_location))
        if not client:
            return

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

    def handle_response(self, response: 'Optional[Union[Dict,List]]') -> None:
        self.is_request_pending = False
        _last_row, last_col = self.view.rowcol(self.last_location)

        response_items, response_incomplete = parse_completion_response(response)
        self.response_items = response_items
        self.response_incomplete = response_incomplete
        self.completions = list(format_completion(item, last_col, settings) for item in self.response_items)

        # if insert_best_completion was just ran, undo it before presenting new completions.
        prev_char = self.view.substr(self.view.sel()[0].begin() - 1)
        if prev_char.isspace():
            if last_text_command == "insert_best_completion":
                self.view.run_command("undo")

        if settings.complete_all_chars or prev_char in self.trigger_chars:
            self.update_completions()

    def handle_error(self, error: dict) -> None:
        self.is_request_pending = False
        sublime.status_message('Completion error: ' + str(error.get('message')))

    def update_completions(self) -> None:
        if self.view.is_auto_complete_visible():
            self.view.run_command("hide_auto_complete")

        def _show_auto_complete() -> None:
                self.view.run_command("auto_complete", {
                    'disable_auto_insert': True,
                    'api_completions_only': settings.only_show_lsp_completions,
                    'next_completion_if_showing': False
                })

        sublime.set_timeout(_show_auto_complete, 0)
