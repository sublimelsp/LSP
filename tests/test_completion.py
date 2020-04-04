from LSP.plugin.completion import CompletionHandler
from LSP.plugin.core.registry import is_supported_view
from LSP.plugin.core.typing import Any, Generator, List, Dict, Optional
from setup import CI, SUPPORTED_SYNTAX, TextDocumentTestCase, add_config, remove_config, text_config
from unittesting import DeferrableTestCase
import sublime


additional_edits = {
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

    def move_cursor(self, row: int, col: int) -> None:
        point = self.view.text_point(row, col)
        # move cursor to point
        s = self.view.sel()
        s.clear()
        s.add(point)

    def select_completion(self) -> 'Generator':
        current_change_count = self.view.change_count()
        self.view.run_command('auto_complete')
        committed = False

        def commit_completion() -> bool:
            if not self.view.is_auto_complete_visible():
                return False
            nonlocal committed
            if not committed:
                self.view.run_command("commit_completion")
                committed = True
            return self.view.change_count() > current_change_count

        yield commit_completion

    def read_file(self) -> str:
        return self.view.substr(sublime.Region(0, self.view.size()))

    def verify(self, response: List[Dict[str, Any]], expected_text: str,
               pre_insert_text: Optional[str] = None) -> Generator:
        if isinstance(pre_insert_text, str):
            self.type(pre_insert_text)
        self.set_response("textDocument/completion", response)
        yield from self.select_completion()
        yield from self.await_message("textDocument/completion")
        self.assertEqual(self.read_file(), expected_text)

    def test_none(self) -> 'Generator':
        self.set_response("textDocument/completion", None)
        self.view.run_command('auto_complete')
        yield lambda: self.view.is_auto_complete_visible()

    def test_simple_label(self) -> 'Generator':
        yield from self.verify([{'label': 'asdf'}, {'label': 'efcgh'}], 'asdf')

    def test_prefer_insert_text_over_label(self) -> 'Generator':
        yield from self.verify([{"label": "Label text", "insertText": "Insert text"}], 'Insert text')

    def test_prefer_text_edit_over_insert_text(self) -> 'Generator':
        yield from self.verify([{
            "label": "Label text",
            "insertText": "Insert text",
            "textEdit": {
                "newText": "Text edit",
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
            }}], 'Text edit')

    def test_simple_insert_text(self) -> 'Generator':
        yield from self.verify([{'label': 'asdf', 'insertText': 'asdf()'}], 'asdf()', "a")

    def test_var_prefix_using_label(self) -> 'Generator':
        yield from self.verify([{'label': '$what'}], "$what", "$")

    def test_var_prefix_added_in_insertText(self) -> 'Generator':
        """
        Powershell: label='true', insertText='$true' (see https://github.com/sublimelsp/LSP/issues/294)
        """
        yield from self.verify([{
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
            }}], "$true", "$")

    def test_var_prefix_added_in_label(self) -> 'Generator':
        """
        PHP language server: label='$someParam', textEdit='someParam' (https://github.com/sublimelsp/LSP/issues/368)
        """
        yield from self.verify([{
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
            }}], "$what", "$")

    def test_space_added_in_label(self) -> 'Generator':
        """
        Clangd: label=" const", insertText="const" (https://github.com/sublimelsp/LSP/issues/368)
        """
        yield from self.verify([{'label': ' const', 'insertText': 'const'}], "const")

    def test_dash_missing_from_label(self) -> 'Generator':
        """
        Powershell: label="UniqueId", insertText="-UniqueId" (https://github.com/sublimelsp/LSP/issues/572)
        """
        yield from self.verify([{
            'label': 'UniqueId',
            'insertText': '-UniqueId',
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
            }}], "-UniqueId", "u")

    def test_edit_before_cursor(self) -> 'Generator':
        """
        Metals: label="override def myFunction(): Unit"
        """
        yield from self.verify([{
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
            }}], '  override def myFunction(): Unit = ???', '  def myF')

    def test_edit_after_nonword(self) -> 'Generator':
        """
        Metals: List.| selects label instead of textedit
        See https://github.com/sublimelsp/LSP/issues/645
        """
        yield from self.verify([{
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
            }}], 'List.apply()', "List.")

    def test_implement_all_members_quirk(self) -> 'Generator':
        """
        Metals: "Implement all members" should just select the newText.
        https://github.com/sublimelsp/LSP/issues/771
        """
        yield from self.verify([{
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
            }}], 'def foo: Int = ???\n   def boo: Int = ???', "I")

    def test_additional_edits(self) -> 'Generator':
        yield from self.verify([{
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
            ]}], 'import asdf;\nasdf')

    def test_resolve_for_additional_edits(self) -> 'Generator':
        self.set_response('textDocument/completion', [{'label': 'asdf'}, {'label': 'efcgh'}])
        self.set_response('completionItem/resolve', additional_edits)

        yield from self.select_completion()
        yield from self.await_message('textDocument/completion')
        yield from self.await_message('completionItem/resolve')

        self.assertEquals(
            self.read_file(),
            'import asdf;\nasdf')

    def test_apply_additional_edits_only_once(self) -> 'Generator':
        self.set_response('textDocument/completion', [{'label': 'asdf'}, {'label': 'efcgh'}])
        self.set_response('completionItem/resolve', additional_edits)

        yield from self.select_completion()
        yield from self.await_message('textDocument/completion')

        self.assertEquals(
            self.read_file(),
            'import asdf;\nasdf')

    def test_prefix_should_include_the_dollar_sign(self):
        self.set_response(
            'textDocument/completion',
            {
                "items":
                [
                    {
                        "label": "$hello",
                        "textEdit":
                        {
                            "newText": "$hello",
                            "range": {"end": {"line": 2, "character": 3}, "start": {"line": 2, "character": 0}}
                        },
                        "data": 2369386987913238,
                        "detail": "int",
                        "kind": 6,
                        "sortText": "$hello"
                    }
                ],
                "isIncomplete": False
            })

        self.type('<?php\n$hello = "world";\n$he\n?>\n')
        # move cursor after `$he|`
        self.move_cursor(2, 3)
        yield from self.select_completion()
        yield from self.await_message('textDocument/completion')

        self.assertEquals(self.read_file(), '<?php\n$hello = "world";\n$hello\n?>\n')
