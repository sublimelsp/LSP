from LSP.plugin.completion import CompletionHandler
from LSP.plugin.core.registry import is_supported_view
from setup import CI, SUPPORTED_SYNTAX, TextDocumentTestCase, add_config, remove_config, text_config
from unittesting import DeferrableTestCase
import sublime


try:
    from typing import Dict, Optional, List, Generator
    assert Dict and Optional and List and Generator
except ImportError:
    pass

label_completions = [{'label': 'asdf'}, {'label': 'efcgh'}]
completion_with_additional_edits = [
    {
        'label': 'asdf',
        'additionalTextEdits': [
            {
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
            }
        ]
    }
]
insert_text_completions = [{'label': 'asdf', 'insertText': 'asdf()'}]
var_completion_using_label = [{'label': '$what'}]
var_prefix_added_in_insertText = [
    {
        "insertText": "$true",
        "label": "true",
        "textEdit": {
            "newText": "$true",
            "range": {
                "end": {
                    "character": 5,
                    "line": 0
                },
                "start": {
                    "character": 0,
                    "line": 0
                }
            }
        }
    }
]
var_prefix_added_in_label = [
    {
        'label': '$what',
        'textEdit': {
            'range': {
                'start': {
                    'line': 0,
                    'character': 0
                },
                'end': {
                    'line': 0,
                    'character': 1
                }
            },
            'newText': '$what'
        }
    }
]
space_added_in_label = [{'label': ' const', 'insertText': 'const'}]

dash_missing_from_label = [
    {
        'label': 'UniqueId',
        'textEdit': {
            'range': {
                'start': {
                    'character': 0,
                    'line': 0
                },
                'end': {
                    'character': 1,
                    'line': 0
                }
            },
            'newText': '-UniqueId'
        },
        'insertText': '-UniqueId'
    }
]

edit_before_cursor = [
    {
        'insertTextFormat': 2,
        'label': 'override def myFunction(): Unit',
        'textEdit': {
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
        }
    }
]

edit_after_nonword = [
    {
        'insertTextFormat': 2,
        'label': 'apply[A](xs: A*): List[A]',
        'textEdit': {
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
        }
    }
]

metals_implement_all_members = [
    {
        'insertTextFormat': 2,
        'label': 'Implement all members',
        'textEdit': {
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
        }
    }
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

    def type(self, text: str) -> None:
        self.view.run_command('append', {'characters': text})
        self.view.run_command('move_to', {'to': 'eol'})

    def select_completion(self) -> 'Generator':
        self.view.run_command('auto_complete')

        yield 100
        self.view.run_command("commit_completion")

    def read_file(self) -> str:
        return self.view.substr(sublime.Region(0, self.view.size()))

    def test_simple_label(self) -> 'Generator':
        handler = self.get_view_event_listener("on_query_completions")
        handler.test_completions = label_completions

        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("a", [0])
            yield from self.select_completion()

            self.assertEquals(self.read_file(), 'asdf')

    def test_simple_inserttext(self) -> 'Generator':
        handler = self.get_view_event_listener("on_query_completions")
        handler.test_completions = insert_text_completions

        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("a", [0])
            yield from self.select_completion()

            self.assertEquals(
                self.read_file(),
                insert_text_completions[0]["insertText"])

    def test_var_prefix_using_label(self) -> 'Generator':
        handler = self.get_view_event_listener("on_query_completions")
        handler.test_completions = var_completion_using_label

        self.assertIsNotNone(handler)
        if handler:
            self.type("$")
            yield from self.select_completion()

            self.assertEquals(self.read_file(), '$what')

    def test_var_prefix_added_in_insertText(self) -> 'Generator':
        """

        Powershell: label='true', insertText='$true' (see https://github.com/sublimelsp/LSP/issues/294)

        """
        handler = self.get_view_event_listener("on_query_completions")
        handler.test_completions = var_prefix_added_in_insertText

        self.assertIsNotNone(handler)
        if handler:
            self.type("$")
            yield from self.select_completion()

            self.assertEquals(
                self.read_file(), '$true')

    def test_var_prefix_added_in_label(self) -> 'Generator':
        """

        PHP language server: label='$someParam', textEdit='someParam' (https://github.com/sublimelsp/LSP/issues/368)

        """
        handler = self.get_view_event_listener("on_query_completions")
        handler.test_completions = var_prefix_added_in_label

        self.assertIsNotNone(handler)
        if handler:
            self.type("$")
            yield from self.select_completion()

            self.assertEquals(
                self.read_file(), '$what')

    def test_space_added_in_label(self) -> 'Generator':
        """

        Clangd: label=" const", insertText="const" (https://github.com/sublimelsp/LSP/issues/368)

        """
        handler = self.get_view_event_listener("on_query_completions")
        handler.test_completions = space_added_in_label

        self.assertIsNotNone(handler)
        if handler:
            self.type("")
            handler.on_query_completions("", [0])
            yield from self.select_completion()

            self.assertEquals(
                self.read_file(), 'const')

    def test_dash_missing_from_label(self) -> 'Generator':
        """

        Powershell: label="UniqueId", insertText="-UniqueId" (https://github.com/sublimelsp/LSP/issues/572)

        """
        handler = self.get_view_event_listener("on_query_completions")
        handler.test_completions = dash_missing_from_label

        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("u", [0])
            yield from self.select_completion()

            self.assertEquals(
                self.read_file(),
                '-UniqueId')

    def test_edit_before_cursor(self) -> 'Generator':
        """

        Metals: label="override def myFunction(): Unit"

        """
        handler = self.get_view_event_listener("on_query_completions")
        handler.test_completions = edit_before_cursor

        self.assertIsNotNone(handler)
        if handler:
            self.type('  ')
            handler.on_query_completions("myF", [7])
            yield from self.select_completion()
            self.assertEquals(
                self.read_file(),
                '  override def myFunction(): Unit = ???')

    def test_edit_after_nonword(self) -> 'Generator':
        """

        Metals: List.| selects label instead of textedit
        See https://github.com/sublimelsp/LSP/issues/645

        """
        handler = self.get_view_event_listener("on_query_completions")
        handler.test_completions = edit_after_nonword

        self.assertIsNotNone(handler)
        if handler:
            self.type("List.")
            handler.on_query_completions("", [0])
            yield from self.select_completion()

            self.assertEquals(
                self.read_file(),
                'List.apply()')

    def test_implement_all_members_quirk(self) -> 'Generator':
        """
        Metals: "Implement all members" should just select the newText.
        https://github.com/sublimelsp/LSP/issues/771
        """
        handler = self.get_view_event_listener("on_query_completions")
        handler.test_completions = metals_implement_all_members

        self.assertIsNotNone(handler)
        if handler:
            self.type("I")
            handler.on_query_completions("I", [0])
            yield from self.select_completion()

            self.assertEquals(
                self.read_file(),
                'def foo: Int = ???\n   def boo: Int = ???')

    def test_additional_edits(self) -> 'Generator':
        handler = self.get_view_event_listener("on_query_completions")
        handler.test_completions = completion_with_additional_edits

        self.assertIsNotNone(handler)
        if handler:
            handler.on_query_completions("", [0])
            yield from self.select_completion()

            self.assertEquals(
                self.read_file(),
                'import asdf;\nasdf')

    # def test_resolve_for_additional_edits(self) -> 'Generator':
    #     self.set_response('textDocument/completion', label_completions)
    #     self.set_response('completionItem/resolve', completion_with_additional_edits[0])

    #     handler = self.get_view_event_listener("on_query_completions")
    #     self.assertIsNotNone(handler)
    #     if handler:
    #         handler.on_query_completions("", [0])

    #         # note: ideally the handler is initialized with resolveProvider capability
    #         handler.resolve = True

    #         yield from self.await_message('textDocument/completion')
    #         # note: invoking on_text_command manually as sublime doesn't call it.
    #         handler.on_text_command('commit_completion', {})
    #         original_change_count = self.view.change_count()
    #         self.view.run_command("commit_completion", {})
    #         yield from self.await_view_change(original_change_count + 2)
    #         yield from self.await_message('completionItem/resolve')
    #         yield from self.await_view_change(original_change_count + 2)  # XXX: no changes?
    #         self.assertEquals(
    #             self.read_file(),
    #             'import asdf;\nasdf')
    #         handler.resolve = False
