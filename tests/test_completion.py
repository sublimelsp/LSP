from LSP.plugin.completion import CompletionHandler
from LSP.plugin.core.registry import is_supported_view
from LSP.plugin.core.typing import Any, Generator, List, Dict, Callable
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

    def create_commit_completion_closure(self) -> Callable[[], bool]:
        committed = False
        current_change_count = self.view.change_count()

        def commit_completion() -> bool:
            if not self.view.is_auto_complete_visible():
                return False
            nonlocal committed
            nonlocal current_change_count
            if not committed:
                self.view.run_command("commit_completion")
                committed = True
            return self.view.change_count() > current_change_count

        return commit_completion

    def select_completion(self) -> 'Generator':
        self.view.run_command('auto_complete')
        yield self.create_commit_completion_closure()

    def read_file(self) -> str:
        return self.view.substr(sublime.Region(0, self.view.size()))

    def verify(self, *, completion_items: List[Dict[str, Any]], insert_text: str, expected_text: str) -> Generator:
        if insert_text:
            self.type(insert_text)
        self.set_response("textDocument/completion", completion_items)
        yield from self.select_completion()
        yield from self.await_message("textDocument/completion")
        self.assertEqual(self.read_file(), expected_text)

    def test_none(self) -> 'Generator':
        self.set_response("textDocument/completion", None)
        self.view.run_command('auto_complete')
        yield lambda: self.view.is_auto_complete_visible()

    def test_simple_label(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{'label': 'asdf'}, {'label': 'efcgh'}],
            insert_text='',
            expected_text='asdf')

    def test_prefer_insert_text_over_label(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{"label": "Label text", "insertText": "Insert text"}],
            insert_text='',
            expected_text='Insert text')

    def test_prefer_text_edit_over_insert_text(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{
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
                }
            }],
            insert_text='',
            expected_text='Text edit')

    def test_simple_insert_text(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{'label': 'asdf', 'insertText': 'asdf()'}],
            insert_text="a",
            expected_text='asdf()')

    def test_var_prefix_using_label(self) -> 'Generator':
        yield from self.verify(completion_items=[{'label': '$what'}], insert_text="$", expected_text="$what")

    def test_var_prefix_added_in_insertText(self) -> 'Generator':
        """
        https://github.com/sublimelsp/LSP/issues/294

        User types '$env:U', server replaces '$env:U' with '$env:USERPROFILE'
        """
        yield from self.verify(
            completion_items=[{
                'filterText': '$env:USERPROFILE',
                'insertText': '$env:USERPROFILE',
                'sortText': '0006USERPROFILE',
                'label': 'USERPROFILE',
                'additionalTextEdits': None,
                'detail': None,
                'data': None,
                'kind': 6,
                'command': None,
                'textEdit': {
                    'newText': '$env:USERPROFILE',
                    'range': {
                        'end': {'line': 0, 'character': 6},
                        'start': {'line': 0, 'character': 0}
                    }
                },
                'commitCharacters': None,
                'range': None,
                'documentation': None
            }],
            insert_text="$env:U",
            expected_text="$env:USERPROFILE")

    def test_pure_insertion_text_edit(self) -> 'Generator':
        """
        https://github.com/sublimelsp/LSP/issues/368

        User types '$so', server returns pure insertion completion 'meParam', completing it to '$someParam'.

        THIS TEST FAILS
        """
        yield from self.verify(
            completion_items=[{
                'textEdit': {
                    'newText': 'meParam',
                    'range': {
                        'end': {'character': 4, 'line': 0},
                        'start': {'character': 4, 'line': 0}  # pure insertion!
                    }
                },
                'label': '$someParam',
                'filterText': None,
                'data': None,
                'command': None,
                'detail': 'null',
                'insertText': None,
                'additionalTextEdits': None,
                'sortText': None,
                'documentation': None,
                'kind': 6
            }],
            insert_text="$so",
            expected_text="$someParam")

    def test_space_added_in_label(self) -> 'Generator':
        """
        Clangd: label=" const", insertText="const" (https://github.com/sublimelsp/LSP/issues/368)
        """
        yield from self.verify(
            completion_items=[{
                "label": " const",
                "sortText": "3f400000const",
                "kind": 14,
                "textEdit": {
                    "newText": "const",
                    "range": {
                        "end": {
                            "character": 1,
                            "line": 0
                        },
                        "start": {
                            "character": 3,
                            "line": 0
                        }
                    }
                },
                "insertTextFormat": 2,
                "insertText": "const",
                "filterText": "const",
                "score": 6
            }],
            insert_text=' co',
            expected_text=" const")  # NOT 'const'

    def test_dash_missing_from_label(self) -> 'Generator':
        """
        Powershell: label="UniqueId", trigger="-UniqueIdd, text to be inserted = "-UniqueId"

        (https://github.com/sublimelsp/LSP/issues/572)
        """
        yield from self.verify(
            completion_items=[{
                "filterText": "-UniqueId",
                "documentation": None,
                "textEdit": {
                    "range": {
                        "start": {"character": 14, "line": 0},
                        "end": {"character": 15, "line": 0}
                    },
                    "newText": "-UniqueId"
                },
                "commitCharacters": None,
                "command": None,
                "label": "UniqueId",
                "insertText": "-UniqueId",
                "additionalTextEdits": None,
                "data": None,
                "range": None,
                "insertTextFormat": 1,
                "sortText": "0001UniqueId",
                "kind": 6,
                "detail": "[string[]]"
            }],
            insert_text="u",
            expected_text="-UniqueId")

    def test_edit_before_cursor(self) -> 'Generator':
        """
        Metals: label="override def myFunction(): Unit"
        """
        yield from self.verify(
            completion_items=[{
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
                            'character': 7
                        }
                    }
                }
            }],
            insert_text='  def myF',
            expected_text='  override def myFunction(): Unit = ???')

    def test_edit_after_nonword(self) -> 'Generator':
        """
        https://github.com/sublimelsp/LSP/issues/645
        """
        yield from self.verify(
            completion_items=[{
                "textEdit": {
                    "newText": "apply($0)",
                    "range": {
                        "end": {
                            "line": 0,
                            "character": 5
                        },
                        "start": {
                            "line": 0,
                            "character": 5
                        }
                    }
                },
                "label": "apply[A](xs: A*): List[A]",
                "sortText": "00000",
                "preselect": True,
                "insertTextFormat": 2,
                "filterText": "apply",
                "data": {
                    "symbol": "scala/collection/immutable/List.apply().",
                    "target": "file:/home/user/workspace/testproject/?id=root"
                },
                "kind": 2
            }],
            insert_text="List.",
            expected_text='List.apply()')

    def test_filter_text_is_not_a_prefix_of_label(self) -> 'Generator':
        """
        Metals: "Implement all members"

        The filterText is 'e', so when the user types 'e', one of the completion items should be
        "Implement all members".

        VSCode doesn't show the filterText in this case; it'll only show "Implement all members".
        c.f. https://github.com/microsoft/language-server-protocol/issues/898#issuecomment-593968008

        In SublimeText, we always show the filterText (a.k.a. trigger).

        This is one of the more confusing and contentious completion items.

        https://github.com/sublimelsp/LSP/issues/771
        """
        yield from self.verify(
            completion_items=[{
                "label": "Implement all members",
                "kind": 12,
                "sortText": "00002",
                "filterText": "e",
                "insertTextFormat": 2,
                "textEdit": {
                    "range": {
                        "start": {"line": 9, "character": 3},
                        "end": {"line": 9, "character": 4}
                    },
                    "newText": "def foo: Int \u003d ${0:???}\n   def boo: Int \u003d ${0:???}"
                },
                "data": {
                    "target": "file:/Users/ckipp/Documents/scala-workspace/test-project/?id\u003droot",
                    "symbol": "local6"
                }
            }],
            insert_text='e',
            expected_text='def foo: Int \u003d ???\n   def boo: Int \u003d ???')

    def test_additional_edits(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{
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
            }],
            insert_text='',
            expected_text='import asdf;\nasdf')

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

    def test_prefix_should_include_the_dollar_sign(self) -> 'Generator':
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

    def test_fuzzy_match_plaintext_insert_text(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{
                'insertTextFormat': 1,
                'label': 'aaba',
                'insertText': 'aaca'
            }],
            insert_text='aa',
            expected_text='aaca')

    def test_fuzzy_match_plaintext_text_edit(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{
                'insertTextFormat': 1,
                'label': 'aaba',
                'textEdit': {
                    'newText': 'aaca',
                    'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 3}}}
            }],
            insert_text='aab',
            expected_text='aaca')

    def test_fuzzy_match_snippet_insert_text(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{
                'insertTextFormat': 2,
                'label': 'aaba',
                'insertText': 'aaca'
            }],
            insert_text='aab',
            expected_text='aaca')

    def test_fuzzy_match_snippet_text_edit(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{
                'insertTextFormat': 2,
                'label': 'aaba',
                'textEdit': {
                    'newText': 'aaca',
                    'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 2}}}
            }],
            insert_text='aab',
            expected_text='aaca')

    def verify_multi_cursor(self, completion: Dict[str, Any]) -> 'Generator':
        """
        This checks whether `fd` gets replaced by `fmod` when the cursor is at `fd|`.
        Turning the `d` into an `m` is an important part of the test.
        """
        self.type('fd\nfd\nfd')
        selection = self.view.sel()
        selection.clear()
        selection.add(sublime.Region(2, 2))
        selection.add(sublime.Region(5, 5))
        selection.add(sublime.Region(8, 8))
        self.assertEqual(len(selection), 3)
        for region in selection:
            self.assertEqual(self.view.substr(self.view.line(region)), "fd")
        self.set_response("textDocument/completion", [completion])
        yield from self.select_completion()
        yield from self.await_message("textDocument/completion")
        self.assertEqual(self.read_file(), 'fmod()\nfmod()\nfmod()')

    def test_multi_cursor_plaintext_insert_text(self) -> 'Generator':
        yield from self.verify_multi_cursor({
            'insertTextFormat': 1,
            'label': 'fmod(a, b)',
            'insertText': 'fmod()'
        })

    def test_multi_cursor_plaintext_text_edit(self) -> 'Generator':
        yield from self.verify_multi_cursor({
            'insertTextFormat': 1,
            'label': 'fmod(a, b)',
            'textEdit': {
                'newText': 'fmod()',
                'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 2}}
            }
        })

    def test_multi_cursor_snippet_insert_text(self) -> 'Generator':
        yield from self.verify_multi_cursor({
            'insertTextFormat': 2,
            'label': 'fmod(a, b)',
            'insertText': 'fmod($0)'
        })

    def test_multi_cursor_snippet_text_edit(self) -> 'Generator':
        yield from self.verify_multi_cursor({
            'insertTextFormat': 2,
            'label': 'fmod(a, b)',
            'textEdit': {
                'newText': 'fmod($0)',
                'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 2}}
            }
        })

    def test_nontrivial_text_edit_removal(self) -> 'Generator':
        self.type('#include <u>')
        self.move_cursor(0, 11)  # Put the cursor inbetween 'u' and '>'
        self.set_response("textDocument/completion", [{
            'filterText': 'uchar.h>',
            'label': ' uchar.h>',
            'textEdit': {
                # This range should remove "u>" and then insert "uchar.h>"
                'range': {'start': {'line': 0, 'character': 10}, 'end': {'line': 0, 'character': 12}},
                'newText': 'uchar.h>'
            },
            'insertText': 'uchar.h>',
            'kind': 17,
            'insertTextFormat': 2
        }])
        yield from self.select_completion()
        yield from self.await_message("textDocument/completion")
        self.assertEqual(self.read_file(), '#include <uchar.h>')

    def test_nontrivial_text_edit_removal_with_buffer_modifications_clangd(self) -> 'Generator':
        self.type('#include <u>')
        self.move_cursor(0, 11)  # Put the cursor inbetween 'u' and '>'
        self.set_response("textDocument/completion", [{
            'filterText': 'uchar.h>',
            'label': ' uchar.h>',
            'textEdit': {
                # This range should remove "u>" and then insert "uchar.h>"
                'range': {'start': {'line': 0, 'character': 10}, 'end': {'line': 0, 'character': 12}},
                'newText': 'uchar.h>'
            },
            'insertText': 'uchar.h>',
            'kind': 17,
            'insertTextFormat': 2
        }])
        self.view.run_command('auto_complete')  # show the AC widget
        yield from self.await_message("textDocument/completion")
        yield 100
        self.view.run_command('insert', {'characters': 'c'})  # type characters
        yield 100
        self.view.run_command('insert', {'characters': 'h'})  # while the AC widget
        yield 100
        self.view.run_command('insert', {'characters': 'a'})  # is visible
        yield 100
        # Commit the completion. The buffer has been modified in the meantime, so the old text edit that says to
        # remove "u>" is invalid. The code in completion.py must be able to handle this.
        yield self.create_commit_completion_closure()
        self.assertEqual(self.read_file(), '#include <uchar.h>')

    def test_nontrivial_text_edit_removal_with_buffer_modifications_json(self) -> 'Generator':
        self.type('{"k"}')
        self.move_cursor(0, 3)  # Put the cursor inbetween 'k' and '"'
        self.set_response("textDocument/completion", [{
            'kind': 10,
            'documentation': 'Array of single or multiple keys',
            'insertTextFormat': 2,
            'label': 'keys',
            'textEdit': {
                # This range should remove '"k"' and then insert '"keys": []'
                'range': {'start': {'line': 0, 'character': 1}, 'end': {'line': 0, 'character': 4}},
                'newText': '"keys": [$1]'
            },
            "filterText": '"keys"',
            "insertText": 'keys": [$1]'
        }])
        self.view.run_command('auto_complete')  # show the AC widget
        yield from self.await_message("textDocument/completion")
        yield 100
        self.view.run_command('insert', {'characters': 'e'})  # type characters
        yield 100
        self.view.run_command('insert', {'characters': 'y'})  # while the AC widget is open
        yield 100
        # Commit the completion. The buffer has been modified in the meantime, so the old text edit that says to
        # remove '"k"' is invalid. The code in completion.py must be able to handle this.
        yield self.create_commit_completion_closure()
        self.assertEqual(self.read_file(), '{"keys": []}')
