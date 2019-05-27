from unittesting import DeferrableTestCase
import sublime
from LSP.plugin.completion import CompletionHandler, CompletionState
from setup import (SUPPORTED_SYNTAX, text_config, add_config, remove_config,
                   TextDocumentTestCase)

try:
    from typing import Dict, Optional, List
    assert Dict and Optional and List
except ImportError:
    pass

label_completions = [dict(label='asdf'), dict(label='efgh')]
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
    def _verify_completes_to(self, completions: 'List[Dict]', result: str):
        yield 100
        self.client.responses['textDocument/completion'] = completions

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
            self.assertEquals(mask, 0)

            # now wait for server response
            yield 100
            self.assertEquals(handler.state, CompletionState.IDLE)
            self.assertEquals(len(handler.completions), 2)

            # verify insertion works
            self.view.run_command("insert_best_completion")
            self.assertEquals(
                self.view.substr(sublime.Region(0, self.view.size())), result)

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
