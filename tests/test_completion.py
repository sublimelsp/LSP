from unittesting import DeferrableTestCase
import sublime
from LSP.plugin.completion import CompletionHandler, CompletionState
from setup import (
    SUPPORTED_SYNTAX, text_config, add_config, remove_config, TextDocumentTestCase
)

try:
    from typing import Dict, Optional
    assert Dict and Optional
except ImportError:
    pass


completions = [dict(label='asdf'), dict(label='efgh')]


class InitializationTests(DeferrableTestCase):

    def setUp(self):
        self.view = sublime.active_window().new_file()
        add_config(text_config)

    def test_is_not_applicable(self):
        self.assertFalse(CompletionHandler.is_applicable(dict()))

    def test_is_applicable(self):
        self.assertTrue(CompletionHandler.is_applicable(dict(syntax=SUPPORTED_SYNTAX)))

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

    def test_enabled(self):
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
            self.assertEquals(self.view.substr(sublime.Region(0, self.view.size())), completions[0]["label"])
