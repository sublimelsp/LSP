import sublime
from LSP.plugin.completion import CompletionHandler, CompletionState
from unittesting import DeferrableTestCase
from setup import (SUPPORTED_SYNTAX, text_config, add_config, remove_config,
                   TextDocumentTestCase)

try:
    from typing import Dict, Optional, List
    assert Dict and Optional and List
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
                     'character': 6
                 },
                 'end': {
                     'line': 0,
                     'character': 6
                 }
             }
         })
]


class InitializationTests(DeferrableTestCase):
    def setUp(self):
        self.view = sublime.active_window().new_file()
        add_config(text_config)

    def test_is_not_applicable(self):
        self.assertFalse(CompletionHandler.is_applicable(dict()))

    def test_is_applicable(self):
        self.assertTrue(
            CompletionHandler.is_applicable(dict(syntax=SUPPORTED_SYNTAX)))

    def test_not_enabled(self):
        handler = CompletionHandler(self.view)
        self.assertFalse(handler.initialized)
        self.assertFalse(handler.enabled)
        result = handler.on_query_completions("", [0])
        yield 100
        self.assertTrue(handler.initialized)
        self.assertFalse(handler.enabled)
        self.assertIsNone(result)

    def tearDown(self):
        remove_config(text_config)
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")


class QueryCompletionsTests(TextDocumentTestCase):
    def test_simple_label(self):
        yield 100
        self.client.responses['textDocument/completion'] = label_completions

        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            # todo: want to test trigger chars instead?
            # self.view.run_command('insert', {"characters": '.'})
            result = handler.on_query_completions("", [1])

            # synchronous response
            self.assertTrue(handler.initialized)
            self.assertTrue(handler.enabled)
            self.assertIsNotNone(result)
            items, mask = result
            self.assertEquals(len(items), 0)
            # self.assertEquals(mask, 0)

            # now wait for server response
            yield 100
            self.assertEquals(handler.state, CompletionState.IDLE)
            self.assertEquals(len(handler.completions), 2)

            # verify insertion works
            self.view.run_command("insert_best_completion")
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())), 'asdf')

    def test_simple_inserttext(self):
        yield 100
        self.client.responses[
            'textDocument/completion'] = insert_text_completions
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [1])
            yield 100
            self.view.run_command("insert_best_completion")
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())),
                insert_text_completions[0]["insertText"])

    def test_var_prefix_using_label(self):
        yield 100
        self.view.run_command('append', {'characters': '$'})
        self.view.run_command('move_to', {'to': 'eol'})
        self.client.responses[
            'textDocument/completion'] = var_completion_using_label
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [1])
            yield 100
            self.view.run_command("insert_best_completion")
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())), '$what')

    def test_var_prefix_added_in_insertText(self):
        """

        Powershell: label='true', insertText='$true' (see https://github.com/tomv564/LSP/issues/294)

        """
        yield 100
        self.view.run_command('append', {'characters': '$'})
        self.view.run_command('move_to', {'to': 'eol'})
        self.client.responses[
            'textDocument/completion'] = var_prefix_added_in_insertText
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [1])
            yield 100
            self.view.run_command("insert_best_completion")
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())), '$what')

    def test_var_prefix_added_in_label(self):
        """

        PHP language server: label='$someParam', textEdit='someParam' (https://github.com/tomv564/LSP/issues/368)

        """
        yield 100
        self.view.run_command('append', {'characters': '$'})
        self.view.run_command('move_to', {'to': 'eol'})
        self.client.responses[
            'textDocument/completion'] = var_prefix_added_in_label
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [1])
            yield 100
            self.view.run_command("insert_best_completion")
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())), '$what')

    def test_space_added_in_label(self):
        """

        Clangd: label=" const", insertText="const" (https://github.com/tomv564/LSP/issues/368)

        """
        yield 100
        self.client.responses['textDocument/completion'] = space_added_in_label
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [1])
            yield 100
            self.view.run_command("insert_best_completion")
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())), 'const')

    def test_dash_missing_from_label(self):
        """

        Powershell: label="UniqueId", insertText="-UniqueId" (https://github.com/tomv564/LSP/issues/572)

        """
        yield 100
        self.view.run_command('append', {'characters': '-'})
        self.view.run_command('move_to', {'to': 'eol'})

        self.client.responses[
            'textDocument/completion'] = dash_missing_from_label
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [1])
            yield 100
            self.view.run_command("insert_best_completion")
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())),
                '-UniqueId')

    def test_edit_before_cursor(self):
        """

        Metals: label="override def myFunction(): Unit"

        """
        yield 100
        self.view.run_command('append', {'characters': '  def myF'})
        self.view.run_command('move_to', {'to': 'eol'})

        self.client.responses['textDocument/completion'] = edit_before_cursor
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("myF", [7])
            yield 100
            # note: invoking on_text_command manually as sublime doesn't call it.
            handler.on_text_command('insert_best_completion', {})
            self.view.run_command("insert_best_completion", {})
            yield 100
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())),
                '  override def myFunction(): Unit = ???')

    def test_edit_after_nonword(self):
        """

        Metals: List.| selects label instead of textedit
        See https://github.com/tomv564/LSP/issues/645

        """
        yield 100
        self.view.run_command('append', {'characters': 'List.'})
        self.view.run_command('move_to', {'to': 'eol'})

        self.client.responses['textDocument/completion'] = edit_after_nonword
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [6])
            yield 100
            # note: invoking on_text_command manually as sublime doesn't call it.
            handler.on_text_command('insert_best_completion', {})
            self.view.run_command("insert_best_completion", {})
            yield 100
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())),
                'List.apply()')

    def test_additional_edits(self):
        yield 100
        self.client.responses[
            'textDocument/completion'] = completion_with_additional_edits
        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [1])
            yield 100
            # note: invoking on_text_command manually as sublime doesn't call it.
            handler.on_text_command('insert_best_completion', {})
            self.view.run_command("insert_best_completion", {})
            yield 100
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())),
                'import asdf;\nasdf')

    def test_resolve_for_additional_edits(self):
        yield 100
        self.client.responses['textDocument/completion'] = label_completions
        self.client.responses[
            'completionItem/resolve'] = completion_with_additional_edits[0]

        handler = self.get_view_event_listener("on_query_completions")
        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [1])

            # note: ideally the handler is initialized with resolveProvider capability
            handler.resolve = True

            yield 100
            # note: invoking on_text_command manually as sublime doesn't call it.
            handler.on_text_command('insert_best_completion', {})
            self.view.run_command("insert_best_completion", {})
            yield 100
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())),
                'import asdf;\nasdf')
            handler.resolve = False
