from LSP.plugin.completion import CompletionHandler
from LSP.plugin.completion import CompletionState
from LSP.plugin.core.registry import is_supported_view
from setup import CI, SUPPORTED_SYNTAX, TextDocumentTestCase, add_config, remove_config, text_config
from unittesting import DeferrableTestCase
import sublime


try:
    from typing import Dict, Optional, List, Generator
    assert Dict and Optional and List and Generator
except ImportError:
    pass

label_completions = [dict(label='asdf'), dict(label='efgh')]
completion_with_additional_edits = [
    dict(label='asdf',
         additionalTextEdits=[{
             'range': {
                 'start': {
                     'line': 0,
                     'character': 0
                 },
                 'end': {
                     'line': 0,
                     'character': 0
                 }
             },
             'newText': 'import asdf;\n'
         }])
]
insert_text_completions = [dict(label='asdf', insertText='asdf()')]
var_completion_using_label = [dict(label='$what')]
var_prefix_added_in_insertText = [dict(label='$what', insertText='what')]
var_prefix_added_in_label = [
    dict(label='$what',
         textEdit={
             'range': {
                 'start': {
                     'line': 0,
                     'character': 1
                 },
                 'end': {
                     'line': 0,
                     'character': 1
                 }
             },
             'newText': 'what'
         })
]
space_added_in_label = [dict(label=' const', insertText='const')]

dash_missing_from_label = [
    dict(label='UniqueId',
         textEdit={
             'range': {
                 'start': {
                     'character': 14,
                     'line': 26
                 },
                 'end': {
                     'character': 15,
                     'line': 26
                 }
             },
             'newText': '-UniqueId'
         },
         insertText='-UniqueId')
]

edit_before_cursor = [
    dict(label='override def myFunction(): Unit',
         textEdit={
             'newText': 'override def myFunction(): Unit = ${0:???}',
             'range': {
                 'start': {
                     'line': 0,
                     'character': 2
                 },
                 'end': {
                     'line': 0,
                     'character': 18
                 }
             }
         })
]

edit_after_nonword = [
    dict(label='apply[A](xs: A*): List[A]',
         textEdit={
             'newText': 'apply($0)',
             'range': {
                 'start': {
                     'line': 0,
                     'character': 5
                 },
                 'end': {
                     'line': 0,
                     'character': 5
                 }
             }
         })
]

metals_implement_all_members = [
    dict(label='Implement all members',
         textEdit={
             'newText': 'def foo: Int \u003d ${0:???}\n   def boo: Int \u003d ${0:???}',
             'range': {
                 'start': {
                     'line': 0,
                     'character': 0
                 },
                 'end': {
                     'line': 0,
                     'character': 1
                 }
             }
         })
]


class InitializationTests(DeferrableTestCase):
    def setUp(self) -> 'Generator':
        self.view = sublime.active_window().new_file()
        add_config(text_config)

    def test_is_not_applicable(self) -> None:
        self.assertFalse(CompletionHandler.is_applicable(dict()))

    def test_is_applicable(self) -> None:
        self.assertTrue(CompletionHandler.is_applicable(dict(syntax=SUPPORTED_SYNTAX)))

    def test_not_enabled(self) -> 'Generator':
        self.assertTrue(is_supported_view(self.view))
        handler = CompletionHandler(self.view)
        self.assertFalse(handler.initialized)
        self.assertFalse(handler.enabled)
        result = handler.on_query_completions("", [0])
        yield lambda: handler.initialized
        yield lambda: not handler.enabled
        self.assertIsNone(result)

    def tearDown(self) -> 'Generator':
        remove_config(text_config)
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")


class QueryCompletionsTests(TextDocumentTestCase):

    def init_view_settings(self) -> None:
        super().init_view_settings()
        assert self.view
        self.view.settings().set("auto_complete_selector", "text.plain")

    def await_message(self, msg: str) -> 'Generator':
        if CI:
            yield 500
        yield from super().await_message(msg)

    def test_simple_label(self) -> 'Generator':
        self.set_response('textDocument/completion', label_completions)

        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            # todo: want to test trigger chars instead?
            # self.view.run_command('insert', {"characters": '.'})
            result = handler.on_query_completions("", [0])

            # synchronous response
            self.assertTrue(handler.initialized)
            self.assertTrue(handler.enabled)
            self.assertIsNotNone(result)
            items, mask = result
            self.assertEquals(len(items), 0)
            # self.assertEquals(mask, 0)

            # now wait for server response
            yield from self.await_message('textDocument/completion')
            self.assertEquals(handler.state, CompletionState.IDLE)
            self.assertEquals(len(handler.completions), 2)

            # verify insertion works
            original_change_count = self.view.change_count()
            self.view.run_command("commit_completion")
            yield from self.await_view_change(original_change_count + 1)
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())), 'asdf')

    def test_simple_inserttext(self) -> 'Generator':
        self.set_response('textDocument/completion', insert_text_completions)
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [0])
            yield from self.await_message('textDocument/completion')
            original_change_count = self.view.change_count()
            self.view.run_command("commit_completion")
            yield from self.await_view_change(original_change_count + 1)
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())),
                insert_text_completions[0]["insertText"])

    def test_var_prefix_using_label(self) -> 'Generator':
        self.view.run_command('append', {'characters': '$'})
        self.view.run_command('move_to', {'to': 'eol'})
        self.set_response('textDocument/completion', var_completion_using_label)
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [1])
            yield from self.await_message('textDocument/completion')
            original_change_count = self.view.change_count()
            self.view.run_command("commit_completion")
            yield from self.await_view_change(original_change_count + 2)
            self.assertEquals(self.view.substr(sublime.Region(0, self.view.size())), '$what')

    def test_var_prefix_added_in_insertText(self) -> 'Generator':
        """

        Powershell: label='true', insertText='$true' (see https://github.com/sublimelsp/LSP/issues/294)

        """
        self.view.run_command('append', {'characters': '$'})
        self.view.run_command('move_to', {'to': 'eol'})
        self.set_response('textDocument/completion', var_prefix_added_in_insertText)
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [1])
            yield from self.await_message('textDocument/completion')
            original_change_count = self.view.change_count()
            self.view.run_command("commit_completion")
            yield from self.await_view_change(original_change_count + 1)
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())), '$what')

    def test_var_prefix_added_in_label(self) -> 'Generator':
        """

        PHP language server: label='$someParam', textEdit='someParam' (https://github.com/sublimelsp/LSP/issues/368)

        """
        self.view.run_command('append', {'characters': '$'})
        self.view.run_command('move_to', {'to': 'eol'})
        self.set_response('textDocument/completion', var_prefix_added_in_label)
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [1])
            yield from self.await_message('textDocument/completion')
            original_change_count = self.view.change_count()
            self.view.run_command("commit_completion")
            yield from self.await_view_change(original_change_count + 1)
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())), '$what')

    def test_space_added_in_label(self) -> 'Generator':
        """

        Clangd: label=" const", insertText="const" (https://github.com/sublimelsp/LSP/issues/368)

        """
        self.set_response('textDocument/completion', space_added_in_label)
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [0])
            yield from self.await_message('textDocument/completion')
            original_change_count = self.view.change_count()
            self.view.run_command("commit_completion")
            yield from self.await_view_change(original_change_count + 1)
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())), 'const')

    def test_dash_missing_from_label(self) -> 'Generator':
        """

        Powershell: label="UniqueId", insertText="-UniqueId" (https://github.com/sublimelsp/LSP/issues/572)

        """
        self.view.run_command('append', {'characters': '-'})
        self.view.run_command('move_to', {'to': 'eol'})

        self.set_response('textDocument/completion', dash_missing_from_label)
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [1])
            yield from self.await_message('textDocument/completion')
            original_change_count = self.view.change_count()
            self.view.run_command("commit_completion")
            yield from self.await_view_change(original_change_count + 2)
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())),
                '-UniqueId')

    def test_edit_before_cursor(self) -> 'Generator':
        """

        Metals: label="override def myFunction(): Unit"

        """
        self.view.run_command('append', {'characters': '  def myF'})
        self.view.run_command('move_to', {'to': 'eol'})

        self.set_response('textDocument/completion', edit_before_cursor)
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("myF", [7])
            yield from self.await_message('textDocument/completion')
            # note: invoking on_text_command manually as sublime doesn't call it.
            handler.on_text_command('commit_completion', {})
            original_change_count = self.view.change_count()
            self.view.run_command("commit_completion", {})
            yield from self.await_view_change(original_change_count + 3)
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())),
                '  override def myFunction(): Unit = ???')

    def test_edit_after_nonword(self) -> 'Generator':
        """

        Metals: List.| selects label instead of textedit
        See https://github.com/sublimelsp/LSP/issues/645

        """
        self.view.run_command('append', {'characters': 'List.'})
        self.view.run_command('move_to', {'to': 'eol'})

        self.set_response('textDocument/completion', edit_after_nonword)
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [5])
            yield from self.await_message('textDocument/completion')
            # note: invoking on_text_command manually as sublime doesn't call it.
            handler.on_text_command('commit_completion', {})
            original_change_count = self.view.change_count()
            self.view.run_command("commit_completion", {})
            yield from self.await_view_change(original_change_count + 1)
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())),
                'List.apply()')

    def test_implement_all_members_quirk(self) -> 'Generator':
        """
        Metals: "Implement all members" should just select the newText.
        https://github.com/sublimelsp/LSP/issues/771
        """
        self.view.run_command('append', {'characters': 'I'})
        self.view.run_command('move_to', {'to': 'eol'})
        self.set_response('textDocument/completion', metals_implement_all_members)
        handler = self.get_view_event_listener('on_query_completions')
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [1])
            yield from self.await_message('textDocument/completion')
            handler.on_text_command('commit_completion', {})
            original_change_count = self.view.change_count()
            self.view.run_command("commit_completion", {})
            yield from self.await_view_change(original_change_count + 2)
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())),
                'def foo: Int = ???\n   def boo: Int = ???')

    def test_additional_edits(self) -> 'Generator':
        self.set_response('textDocument/completion', completion_with_additional_edits)
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [0])
            yield from self.await_message('textDocument/completion')
            # note: invoking on_text_command manually as sublime doesn't call it.
            handler.on_text_command('commit_completion', {})
            original_change_count = self.view.change_count()
            self.view.run_command("commit_completion", {})
            yield from self.await_view_change(original_change_count + 2)
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())),
                'import asdf;\nasdf')

    def test_resolve_for_additional_edits(self) -> 'Generator':
        self.set_response('textDocument/completion', label_completions)
        self.set_response('completionItem/resolve', completion_with_additional_edits[0])

        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [0])

            # note: ideally the handler is initialized with resolveProvider capability
            handler.resolve = True

            yield from self.await_message('textDocument/completion')
            # note: invoking on_text_command manually as sublime doesn't call it.
            handler.on_text_command('commit_completion', {})
            original_change_count = self.view.change_count()
            self.view.run_command("commit_completion", {})
            yield from self.await_view_change(original_change_count + 2)
            yield from self.await_message('completionItem/resolve')
            yield from self.await_view_change(original_change_count + 2)  # XXX: no changes?
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())),
                'import asdf;\nasdf')
            handler.resolve = False
