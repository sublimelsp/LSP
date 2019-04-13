import sublime
import sublime_plugin

try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass

from .core.protocol import Request
from .core.events import global_events
from .core.settings import settings
from .core.logging import debug, exception_log
from .core.protocol import CompletionItemKind
from .core.registry import session_for_view, client_for_view
from .core.configurations import is_supported_syntax
from .core.documents import get_document_position
from .core.sessions import Session

NO_COMPLETION_SCOPES = 'comment, string'
completion_item_kind_names = {v: k for k, v in CompletionItemKind.__dict__.items()}


def extract_trigger(completion_item: 'Dict[str, Any]') -> str:
    if settings.prefer_label_over_filter_text:
        return completion_item["label"]
    else:
        return completion_item.get("filterText", completion_item["label"])


def extract_hint(completion_item: 'Dict[str, Any]') -> 'Optional[str]':
    hint = None
    if settings.completion_hint_type == "auto":
        hint = completion_item.get("detail")
        if not hint:
            kind = completion_item.get("kind")
            if kind:
                hint = completion_item_kind_names[kind]
    elif settings.completion_hint_type == "detail":
        hint = completion_item.get("detail")
    elif settings.completion_hint_type == "kind":
        kind = completion_item.get("kind")
        if kind:
            hint = completion_item_kind_names.get(kind)
    return hint


def extract_replacement(completion_item: 'Dict[str, Any]', fallback: str, prefix: str, word_separators: str) -> str:
    replacement = None
    text_edit = completion_item.get("textEdit")
    if text_edit:
        # Unfortunately the ST API does not naturally allow us to pass along the replacement range.
        replacement = text_edit.get("newText")
    if not replacement:
        replacement = completion_item.get("insertText") or fallback
    if completion_item.get("insertTextFormat", 1) == 1:
        if replacement[0] in word_separators and prefix and prefix[0] not in word_separators:
            repl = replacement[1:]
            for sep in word_separators:
                if sep in repl:
                    replacement = repl
                    break
        replacement = replacement.replace("$", "\\$")
    return replacement


def format_completion(completion_item: 'Dict[str, Any]', prefix: str, word_separators: str) -> 'Tuple[str, str]':
    trigger = extract_trigger(completion_item)
    hint = extract_hint(completion_item)
    replacement = extract_replacement(completion_item, trigger, prefix, word_separators)
    return "{}\t  {}".format(trigger, hint) if hint else trigger, replacement


class CompletionState(object):
    IDLE = 0
    REQUESTING = 1
    APPLYING = 2
    CANCELLING = 3


resolvable_completion_items = []  # type: List[Any]


def find_completion_item(label: str) -> 'Optional[Any]':
    matches = list(filter(lambda i: i.get("label") == label, resolvable_completion_items))
    return matches[0] if matches else None


class CompletionContext(object):

    def __init__(self, begin):
        self.begin = begin  # type: Optional[int]
        self.end = None  # type: Optional[int]
        self.region = None  # type: Optional[sublime.Region]
        self.committing = False

    def committed_at(self, end):
        self.end = end
        self.region = sublime.Region(self.begin, self.end)
        self.committing = False


current_completion = None  # type: Optional[CompletionContext]


def has_resolvable_completions(view):
    session = session_for_view(view)
    if session:
        completionProvider = session.get_capability(
            'completionProvider')
        if completionProvider:
            if completionProvider.get('resolveProvider', False):
                return True
    return False


class CompletionSnippetHandler(sublime_plugin.EventListener):

    def on_query_completions(self, view, prefix, locations):
        global current_completion
        if settings.resolve_completion_for_snippets and has_resolvable_completions(view):
            current_completion = CompletionContext(view.sel()[0].begin())

    def on_text_command(self, view, command_name, args):
        if settings.resolve_completion_for_snippets and current_completion:
            current_completion.committing = command_name in ('commit_completion', 'insert_best_completion')

    def on_modified(self, view):
        global current_completion

        if settings.resolve_completion_for_snippets and view.file_name():
            if current_completion and current_completion.committing:
                current_completion.committed_at(view.sel()[0].end())
                inserted = view.substr(current_completion.region)
                item = find_completion_item(inserted)
                if item:
                    self.resolve_completion(item, view)
                else:
                    current_completion = None

    def resolve_completion(self, item, view):
        session = session_for_view(view)
        if not session:
            return
        if not session.client:
            return

        session.client.send_request(
            Request.resolveCompletionItem(item),
            lambda response: self.handle_resolve_response(response, view))

    def handle_resolve_response(self, response, view):
        # replace inserted text if a snippet was returned.
        if current_completion and response.get('insertTextFormat') == 2:  # snippet
            insertText = response.get('insertText')
            try:
                sel = view.sel()
                sel.clear()
                sel.add(current_completion.region)
                view.run_command("insert_snippet", {"contents": insertText})
            except Exception as err:
                exception_log("Error inserting snippet: " + insertText, err)


last_text_command = None


class CompletionHelper(sublime_plugin.EventListener):
    def on_text_command(self, view, command_name, args):
        global last_text_command
        last_text_command = command_name


class CompletionHandler(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        self.view = view
        self.initialized = False
        self.enabled = False
        self.trigger_chars = []  # type: List[str]
        self.resolve = False
        self.resolve_details = []  # type: List[Tuple[str, str]]
        self.state = CompletionState.IDLE
        self.completions = []  # type: List[Any]
        self.next_request = None  # type: Optional[Tuple[str, List[int]]]
        self.last_prefix = ""
        self.last_location = 0

    @classmethod
    def is_applicable(cls, settings):
        syntax = settings.get('syntax')
        if syntax is not None:
            return is_supported_syntax(syntax)
        else:
            return False

    def initialize(self):
        self.initialized = True
        session = session_for_view(self.view)
        if session:
            completionProvider = session.get_capability(
                'completionProvider')
            if completionProvider:
                self.enabled = True
                self.trigger_chars = completionProvider.get(
                    'triggerCharacters') or []
                self.has_resolve_provider = completionProvider.get('resolveProvider', False)
                if self.trigger_chars:
                    self.register_trigger_chars(session)

    def _view_language(self, config_name: str) -> 'Optional[str]':
        languages = self.view.settings().get('lsp_language')
        return languages.get(config_name) if languages else None

    def register_trigger_chars(self, session: Session) -> None:
        completion_triggers = self.view.settings().get('auto_complete_triggers', [])
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
                        if scope_trigger:
                            scope_trigger['characters'] = "".join(self.trigger_chars)
                        else:
                            completion_triggers.append({
                                'characters': "".join(self.trigger_chars),
                                'selector': scope
                            })

            self.view.settings().set('auto_complete_triggers', completion_triggers)

    def is_after_trigger_character(self, location):
        if location > 0:
            prev_char = self.view.substr(location - 1)
            return prev_char in self.trigger_chars

    def is_same_completion(self, prefix, locations):
        # completion requests from the same location with the same prefix are cached.
        current_start = locations[0] - len(prefix)
        last_start = self.last_location - len(self.last_prefix)
        return prefix.startswith(self.last_prefix) and current_start == last_start

    def on_modified(self):
        # hide completion when backspacing past last completion.
        if self.view.sel()[0].begin() < self.last_location:
            self.last_location = 0
            self.view.run_command("hide_auto_complete")
        # cancel current completion if the previous input is an space
        prev_char = self.view.substr(self.view.sel()[0].begin() - 1)
        if self.state == CompletionState.REQUESTING and prev_char.isspace():
            self.state = CompletionState.CANCELLING

    def on_query_completions(self, prefix, locations):
        if prefix != "" and self.view.match_selector(locations[0], NO_COMPLETION_SCOPES):
            # debug('discarding completion because no completion scope with prefix {}'.format(prefix))
            return (
                [],
                sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS
            )

        if not self.initialized:
            self.initialize()

        if self.enabled:
            reuse_completion = self.is_same_completion(prefix, locations)
            if self.state == CompletionState.IDLE:
                if not reuse_completion:
                    self.last_prefix = prefix
                    self.last_location = locations[0]
                    self.do_request(prefix, locations)
                    self.completions = []

            elif self.state in (CompletionState.REQUESTING, CompletionState.CANCELLING):
                self.next_request = (prefix, locations)
                self.state = CompletionState.CANCELLING

            elif self.state == CompletionState.APPLYING:
                self.state = CompletionState.IDLE

            return (
                self.completions,
                0 if not settings.only_show_lsp_completions
                else sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS
            )

    def do_request(self, prefix: str, locations: 'List[int]'):
        self.next_request = None
        view = self.view

        # don't store client so we can handle restarts
        client = client_for_view(view)
        if not client:
            return

        if settings.complete_all_chars or self.is_after_trigger_character(locations[0]):
            global_events.publish("view.on_purge_changes", self.view)
            document_position = get_document_position(view, locations[0])
            if document_position:
                client.send_request(
                    Request.complete(document_position),
                    lambda response: self.handle_response(prefix, response),
                    self.handle_error)
                self.state = CompletionState.REQUESTING

    def handle_response(self, prefix: str, response: 'Optional[Dict]'):
        global resolvable_completion_items

        if self.state == CompletionState.REQUESTING:
            items = []  # type: List[Dict]
            if isinstance(response, dict):
                items = response["items"] or []
            elif isinstance(response, list):
                items = response
            items = sorted(items, key=lambda item: item.get("sortText") or item["label"])
            word_separators = self.view.settings().get("word_separators") or ""
            self.completions = list(format_completion(item, prefix, word_separators) for item in items)

            if self.has_resolve_provider:
                resolvable_completion_items = items

            # if insert_best_completion was just ran, undo it before presenting new completions.
            prev_char = self.view.substr(self.view.sel()[0].begin() - 1)
            if prev_char.isspace():
                if last_text_command == "insert_best_completion":
                    self.view.run_command("undo")

            self.state = CompletionState.APPLYING
            self.view.run_command("hide_auto_complete")
            self.run_auto_complete()
        elif self.state == CompletionState.CANCELLING:
            self.state = CompletionState.IDLE
            if self.next_request:
                prefix, locations = self.next_request
                self.do_request(prefix, locations)
        else:
            debug('Got unexpected response while in state {}'.format(self.state))

    def handle_error(self, error: dict):
        sublime.status_message('Completion error: ' + str(error.get('message')))
        self.state = CompletionState.IDLE

    def run_auto_complete(self):
        self.view.run_command(
            "auto_complete", {
                'disable_auto_insert': True,
                'api_completions_only': settings.only_show_lsp_completions,
                'next_completion_if_showing': False
            })
