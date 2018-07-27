import unittest
from unittest.mock import MagicMock
import sublime
from LSP.plugin.completion import CompletionHandler, CompletionState
from LSP.plugin.core.settings import client_configs, ClientConfig
from os.path import dirname


def create_completion_item(item: str):
    return {
        "label": item
    }


def create_completion_response(items):
    return {
        "items": list(map(create_completion_item, items))
    }


class FakeClient(object):

    def __init__(self):
        self.response = None
        pass

    def get_capability(self, capability_name: str):
        return {
            'triggerCharacters': ['.'],
            'resolveProvider': False
        }


SUPPORTED_SCOPE = "text.plain"
SUPPORTED_SYNTAX = "Lang.sublime-syntax"
test_client_config = ClientConfig('langls', [], None, [SUPPORTED_SCOPE], [SUPPORTED_SYNTAX], 'lang')
test_file_path = dirname(__file__) + "/testfile.txt"


@unittest.skip('asd')
class InitializationTests(unittest.TestCase):

    def setUp(self):
        self.view = sublime.active_window().new_file()
        self.old_configs = client_configs.all
        client_configs.all = [test_client_config]

    def test_is_not_applicable(self):
        self.assertFalse(CompletionHandler.is_applicable(dict()))

    def test_is_applicable(self):
        self.assertEquals(len(client_configs.all), 1)
        self.assertTrue(CompletionHandler.is_applicable(dict(syntax=SUPPORTED_SYNTAX)))

    def test_not_enabled(self):
        handler = CompletionHandler(self.view)
        self.assertFalse(handler.initialized)
        self.assertFalse(handler.enabled)
        result = handler.on_query_completions("", [0])
        self.assertTrue(handler.initialized)
        self.assertFalse(handler.enabled)
        self.assertIsNone(result)

    def tearDown(self):
        client_configs.all = self.old_configs
        if self.view:
            self.view.set_scratch(True)
            self.view.window().focus_view(self.view)
            self.view.window().run_command("close_file")


@unittest.skip('asf')
class QueryCompletionsTests(unittest.TestCase):

    def setUp(self):
        self.view = sublime.active_window().open_file(test_file_path)
        self.old_configs = client_configs.all
        client_configs.all = [test_client_config]
        self.client = FakeClient()
        # add_window_client(sublime.active_window(), test_client_config.name, self.client)

    def test_enabled(self):
        self.view.run_command('insert', {"characters": '.'})

        self.client.send_request = MagicMock()

        handler = CompletionHandler(self.view)
        self.assertEquals(handler.state, CompletionState.IDLE)

        result = handler.on_query_completions("", [1])
        self.assertIsNotNone(result)
        items, mask = result
        self.assertEquals(len(items), 0)
        self.assertEquals(mask, sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

        self.assertTrue(handler.initialized)
        self.assertTrue(handler.enabled)
        self.assertEquals(handler.state, CompletionState.REQUESTING)

        self.client.send_request.assert_called_once()
        # time.sleep(1000)
        # self.assertEquals(len(handler.completions), 2)
        # self.assertEquals(handler.state, CompletionState.APPLYING)

        # running auto_complete command does not work
        # sublime does not know about the instance we registered here.
        # we do it directly here
        # items, mask = handler.on_query_completions("", [1])

        # self.assertEquals(len(items), 2)
        # self.assertEquals(mask, sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    def tearDown(self):
        client_configs.all = self.old_configs
        if self.view:
            self.view.window().run_command("close_file")
