from unittesting import DeferrableTestCase
import sublime
from LSP.plugin.completion import CompletionHandler, CompletionState
from LSP.plugin.core.settings import client_configs, ClientConfig
from LSP.plugin.core.registry import windows
from os.path import dirname
from LSP.plugin.core.sessions import Session
from LSP.plugin.core.test_session import MockClient

try:
    from typing import Dict, Optional
    assert Dict and Optional
except ImportError:
    pass


SUPPORTED_SCOPE = "text.plain"
SUPPORTED_SYNTAX = "Packages/Text/Plain text.tmLanguage"
test_client_config = ClientConfig('textls', [], None, [SUPPORTED_SCOPE], [SUPPORTED_SYNTAX], 'lang')
test_file_path = dirname(__file__) + "/testfile.txt"

completions = [dict(label='asdf'), dict(label='efgh')]


def sublime_delayer(delay):
    def timeout_function(callable):
        sublime.set_timeout(callable, delay)

    return timeout_function


class InitializationTests(DeferrableTestCase):

    def setUp(self):
        self.view = sublime.active_window().new_file()
        client_configs.all.append(test_client_config)

    def test_is_not_applicable(self):
        self.assertFalse(CompletionHandler.is_applicable(dict()))

    def test_is_applicable(self):
        # self.assertEquals(len(client_configs.all), 1)
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
        client_configs.all.remove(test_client_config)
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")


class QueryCompletionsTests(DeferrableTestCase):

    def setUp(self):
        window = sublime.active_window()
        self.view = window.open_file(test_file_path)
        client_configs.all.append(test_client_config)
        self.client = MockClient(async_response=sublime_delayer(100))
        self.client.responses['textDocument/completion'] = completions
        self.wm = windows.lookup(window)
        session = Session(test_client_config, "", self.client)
        self.wm.update_configs(client_configs.all)
        self.wm._sessions[test_client_config.name] = session
        self.wm._handle_session_started(session, "", test_client_config)

    def test_enabled(self):
        yield 100

        from sublime_plugin import view_event_listeners
        handler = None
        for listener in view_event_listeners[self.view.id()]:
            if "on_query_completions" in dir(listener):
                handler = listener

        # self.assertTrue(CompletionHandler.is_applicable(self.view.settings()))
        # handler = CompletionHandler(self.view)
        self.assertIsNotNone(handler)
        if handler:

            self.assertEquals(handler.state, CompletionState.IDLE)

            # todo: want to test trigger chars?
            # self.view.run_command('insert', {"characters": '.'})
            result = handler.on_query_completions("", [1])

            # from LSP import rpdb
            # rpdb.set_trace()

            self.assertTrue(handler.initialized)
            self.assertTrue(handler.enabled)
            self.assertIsNotNone(result)
            items, mask = result
            self.assertEquals(len(items), 0)
            self.assertEquals(mask, sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

            yield 100
            self.assertEquals(handler.state, CompletionState.IDLE)
            self.assertEquals(len(handler.completions), 2)

            self.view.run_command("insert_best_completion")
            self.assertEquals(self.view.substr(sublime.Region(0, self.view.size())), completions[0]["label"])

    def tearDown(self):
        client_configs.all.remove(test_client_config)
        self.wm._handle_session_ended(test_client_config.name)
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")
