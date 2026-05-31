from __future__ import annotations

from .setup import TextDocumentTestCase
from copy import deepcopy
from LSP.plugin import apply_text_edits
from LSP.plugin import Request
from LSP.plugin.core.protocol import UINT_MAX
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.core.views import entire_content
from typing import Iterable
from typing import TYPE_CHECKING
from unittest import skip
import os
import sublime

if TYPE_CHECKING:
    from LSP.protocol import Command

SELFDIR = os.path.dirname(__file__)
TEST_FILE_PATH = os.path.join(SELFDIR, 'testfile.txt')
GOTO_RESPONSE = [
    {
        'uri': filename_to_uri(TEST_FILE_PATH),
        'range':
        {
            'start':
            {
                # Put the cursor at the capital letter "F".
                'character': 5,
                'line': 1
            },
            'end':
            {
                'character': 5,
                'line': 1
            }
        }
    }
]
GOTO_RESPONSE_LOCATION_LINK = [
    {
        'originSelectionRange': {'start': {'line': 0, 'character': 0}},
        'targetUri': GOTO_RESPONSE[0]['uri'],
        'targetRange': GOTO_RESPONSE[0]['range'],
        'targetSelectionRange': GOTO_RESPONSE[0]['range']
    }
]
GOTO_CONTENT = r'''abcdefghijklmnopqrstuvwxyz
ABCDEFGHIJKLMNOPQRSTUVWXYZ
0123456789
'''


class SingleDocumentTestCase(TextDocumentTestCase):

    def test_did_open(self) -> None:
        # Just the existence of this method checks "initialize" -> "initialized" -> "textDocument/didOpen"
        # -> "shutdown" -> client shut down
        pass

    async def test_out_of_bounds_column_for_text_document_edit(self) -> None:
        self.insert_characters("a\nb\nc\n")
        await apply_text_edits(self.view, [
            {
                'newText': 'hello there',
                'range': {
                    'start': {
                        'line': 1,
                        'character': 0,
                    },
                    'end': {
                        'line': 1,
                        'character': 10000,
                    }
                }
            },
        ])
        self.assertEqual(entire_content(self.view), "a\nhello there\nc\n")

    async def test_did_close(self) -> None:
        self.assertTrue(self.view)
        self.assertTrue(self.view.is_valid())
        self.view.close()
        await self.await_message("textDocument/didClose")

    async def test_sends_save_with_purge(self) -> None:
        assert self.view
        self.view.settings().set("lsp_format_on_save", False)
        self.insert_characters("A")
        self.view.run_command("lsp_save", {'async': True})
        await self.await_message("textDocument/didChange")
        await self.await_message("textDocument/didSave")
        await self.await_clear_view_and_save()

    async def test_formats_on_save(self) -> None:
        assert self.view
        self.view.settings().set("lsp_format_on_save", True)
        self.insert_characters("A")
        await self.await_message("textDocument/didChange")
        await self.mock_response('textDocument/formatting', [{
            'newText': "BBB",
            'range': {
                'start': {'line': 0, 'character': 0},
                'end': {'line': 0, 'character': 1}
            }
        }])
        self.view.run_command("lsp_save", {'async': True})
        await self.await_message("textDocument/formatting")
        await self.await_message("textDocument/didChange")
        await self.await_message("textDocument/didSave")
        text = self.view.substr(sublime.Region(0, self.view.size()))
        self.assertEqual("BBB", text)
        await self.await_clear_view_and_save()

    async def test_hover_popup_visible(self) -> None:
        assert self.view
        await self.mock_response('textDocument/hover', {"contents": "greeting"})
        self.view.run_command('insert', {"characters": "Hello Wrld"})
        self.assertFalse(self.view.is_popup_visible())
        self.view.run_command('lsp_hover', {'point': 3})
        await self.wait_until(self.view.is_popup_visible)

    async def test_remove_line_and_then_insert_at_that_line_at_end(self) -> None:
        original = (
            'a\n'
            'b\n'
            'c'
        )
        file_changes = [
            ((2, 0), (3, 0), ''),  # out-of-bounds end position, but this is fine
            ((3, 0), (3, 0), 'c\n')  # out-of-bounds start and end, this line doesn't exist
        ]
        expected = (
            'a\n'
            'b\n'
            'c\n'
        )
        # Old behavior:
        # 1) first we end up with ('a\n', 'b\n', 'cc\n')
        # 2) then we end up with ('a\n', 'b\n', '')
        # New behavior:
        # 1) line index 3 is "created" ('a\n', 'b\n', 'c\n', c\n'))
        # 2) deletes line index 2.
        await self.__run_formatting_test(original, expected, file_changes)

    async def test_apply_formatting(self) -> None:
        original = (
            '<dom-module id="some-thing">\n'
            '<style></style>\n'
            '<template>\n'
            '</template>\n'
            '</dom-module>\n'
        )
        file_changes = [
            ((0, 28), (1, 0), ''),  # delete first \n
            ((1, 0), (1, 15), ''),  # delete second line (but not the \n)
            ((2, 10), (2, 10), '\n    <style></style>'),  # insert after <template>
        ]
        expected = (
            '<dom-module id="some-thing">\n'
            '<template>\n'
            '    <style></style>\n'
            '</template>\n'
            '</dom-module>\n'
        )
        await self.__run_formatting_test(original, expected, file_changes)

    async def test_apply_formatting_and_preserve_order(self) -> None:
        original = (
            'abcde\n'
            'fghij\n'
        )
        # Note that (1, 2) comes before (0, 1) in the text.
        file_changes = [
            ((1, 2), (1, 2), '4'),  # insert after the g
            ((1, 2), (1, 2), '5'),
            ((1, 2), (1, 3), '6'),  # replace the h
            ((0, 1), (0, 1), '1'),  # insert after a
            ((0, 1), (0, 1), '2'),
            ((0, 1), (0, 1), '3'),
        ]
        expected = (
            'a123bcde\n'
            'fg456ij\n'
        )
        await self.__run_formatting_test(original, expected, file_changes)

    async def test_tabs_are_respected_even_when_translate_tabs_to_spaces_is_set_to_true(self) -> None:
        original = ' ' * 4
        file_changes = [((0, 0), (0, 4), '\t')]
        expected = '\t'
        assert self.view
        self.view.settings().set("translate_tabs_to_spaces", True)
        await self.__run_formatting_test(original, expected, file_changes)
        # Make sure the user's settings haven't changed
        self.assertTrue(self.view.settings().get("translate_tabs_to_spaces"))

    async def __run_formatting_test(
        self,
        original: Iterable[str],
        expected: Iterable[str],
        file_changes: list[tuple[tuple[int, int], tuple[int, int], str]]
    ) -> None:
        assert self.view
        original_change_count = self.insert_characters(''.join(original))
        # self.assertEqual(original_change_count, 1)
        await self.mock_response('textDocument/formatting', [{
            'newText': new_text,
            'range': {
                'start': {'line': start[0], 'character': start[1]},
                'end': {'line': end[0], 'character': end[1]}}} for start, end, new_text in file_changes])
        self.view.run_command('lsp_format_document')
        await self.await_message('textDocument/formatting')
        await self.await_view_change(original_change_count + len(file_changes))
        edited_content = self.view.substr(sublime.Region(0, self.view.size()))
        self.assertEqual(edited_content, ''.join(expected))

    async def __run_goto_test(self, response: list, text_document_request: str, subl_command_suffix: str) -> None:
        assert self.view
        self.insert_characters(GOTO_CONTENT)
        # Put the cursor back at the start of the buffer, otherwise is_at_word fails in goto.py.
        self.view.sel().clear()
        self.view.sel().add(sublime.Region(0, 0))
        method = f'textDocument/{text_document_request}'
        await self.mock_response(method, response)
        self.view.run_command(f'lsp_symbol_{subl_command_suffix}')
        await self.await_message(method)

        def condition() -> bool:
            nonlocal self
            assert self.view
            s = self.view.sel()
            if len(s) != 1:
                return False
            return s[0].begin() > 0

        await self.wait_until(condition)
        first = self.view.sel()[0].begin()
        self.assertEqual(self.view.substr(sublime.Region(first, first + 1)), "F")

    async def test_definition(self) -> None:
        await self.__run_goto_test(GOTO_RESPONSE, 'definition', 'definition')

    async def test_definition_location_link(self) -> None:
        await self.__run_goto_test(GOTO_RESPONSE_LOCATION_LINK, 'definition', 'definition')

    async def test_type_definition(self) -> None:
        await self.__run_goto_test(GOTO_RESPONSE, 'typeDefinition', 'type_definition')

    async def test_type_definition_location_link(self) -> None:
        await self.__run_goto_test(GOTO_RESPONSE_LOCATION_LINK, 'typeDefinition', 'type_definition')

    async def test_declaration(self) -> None:
        await self.__run_goto_test(GOTO_RESPONSE, 'declaration', 'declaration')

    async def test_declaration_location_link(self) -> None:
        await self.__run_goto_test(GOTO_RESPONSE_LOCATION_LINK, 'declaration', 'declaration')

    async def test_implementation(self) -> None:
        await self.__run_goto_test(GOTO_RESPONSE, 'implementation', 'implementation')

    async def test_implementation_location_link(self) -> None:
        await self.__run_goto_test(GOTO_RESPONSE_LOCATION_LINK, 'implementation', 'implementation')

    async def test_expand_selection(self) -> None:
        self.insert_characters("abcba\nabcba\nabcba\n")
        self.view.run_command("lsp_selection_set", {"regions": [(2, 2)]})
        self.assertEqual(len(self.view.sel()), 1)
        self.assertEqual(self.view.substr(self.view.sel()[0]), "")
        self.assertEqual(self.view.substr(self.view.sel()[0].a), "c")
        response = [{
            "parent": {
                "parent": {
                    "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 5}}
                },
                "range": {"start": {"line": 0, "character": 1}, "end": {"line": 0, "character": 3}}
            },
            "range": {"start": {"line": 0, "character": 2}, "end": {"line": 0, "character": 3}}
        }]

        async def expand_and_check(a: int, b: int) -> None:
            await self.mock_response("textDocument/selectionRange", response)
            self.view.run_command("lsp_expand_selection")
            await self.await_message("textDocument/selectionRange")
            await self.wait_until(lambda: self.view.sel()[0] == sublime.Region(a, b))

        await expand_and_check(2, 3)
        await expand_and_check(1, 3)
        await expand_and_check(0, 5)

    async def test_rename(self) -> None:
        self.insert_characters("foo\nfoo\nfoo\n")
        await self.mock_response("textDocument/rename", {
                'changes': {
                    filename_to_uri(TEST_FILE_PATH): [
                        {
                            'range': {'start': {'character': 0, 'line': 0}, 'end': {'character': 3, 'line': 0}},
                            'newText': 'bar'
                        },
                        {
                            'range': {'start': {'character': 0, 'line': 1}, 'end': {'character': 3, 'line': 1}},
                            'newText': 'bar'
                        },
                        {
                            'range':
                            {
                                'start': {'character': 0, 'line': 2},
                                # Check that lsp_apply_document_edit guards for overflow over LSP spec limit of UINT_MAX
                                'end': {'character': UINT_MAX + 1, 'line': 2}
                            },
                            'newText': 'bar'
                        }
                    ]
                }
            }
        )
        self.view.run_command("lsp_selection_set", {"regions": [(0, 0)]})
        self.view.run_command("lsp_symbol_rename", {"new_name": "bar"})
        await self.await_message("textDocument/rename")
        await self.await_view_change(9)
        self.assertEqual(self.view.substr(sublime.Region(0, self.view.size())), "bar\nbar\nbar\n")

    async def test_run_command(self) -> None:
        await self.mock_response("workspace/executeCommand", {"canReturnAnythingHere": "asdf"})
        command: Command = {"command": "foo", "arguments": ["hello", "there", "general", "kenobi"]}
        assert self.session
        result = await self.session.run_command(command, progress=False)
        await self.await_message("workspace/executeCommand")
        self.assertEqual(result, {"canReturnAnythingHere": "asdf"})

    async def test_progress(self) -> None:
        # not sure how this tests $/progress ?
        await self.mock_response("foobar", {"general": "kenobi"})
        assert self.session
        result = self.session.request(Request("foobar", {"hello": "world"}, self.view, progress=True))
        self.assertEqual(await result, {"general": "kenobi"})


class SingleDocumentTestCase2(TextDocumentTestCase):

    async def test_did_change(self) -> None:
        assert self.view
        self.maxDiff = None
        self.insert_characters("A")
        await self.await_message("textDocument/didChange")
        # multiple changes are batched into one didChange notification
        self.insert_characters("B\n")
        self.insert_characters("🙂\n")
        self.insert_characters("D")
        result = await self.await_message("textDocument/didChange")
        self.assertEqual(result, {
            'contentChanges': [
                {'rangeLength': 0, 'range': {'start': {'line': 0, 'character': 1}, 'end': {'line': 0, 'character': 1}}, 'text': 'B'},   # noqa
                {'rangeLength': 0, 'range': {'start': {'line': 0, 'character': 2}, 'end': {'line': 0, 'character': 2}}, 'text': '\n'},  # noqa
                {'rangeLength': 0, 'range': {'start': {'line': 1, 'character': 0}, 'end': {'line': 1, 'character': 0}}, 'text': '🙂'},  # noqa
                # Note that this is character offset (2) is correct (UTF-16).
                {'rangeLength': 0, 'range': {'start': {'line': 1, 'character': 2}, 'end': {'line': 1, 'character': 2}}, 'text': '\n'},  # noqa
                {'rangeLength': 0, 'range': {'start': {'line': 2, 'character': 0}, 'end': {'line': 2, 'character': 0}}, 'text': 'D'}],  # noqa
            'textDocument': {
                'version': self.view.change_count(),
                'uri': filename_to_uri(TEST_FILE_PATH)
            }
        })


class SingleDocumentTestCase3(TextDocumentTestCase):

    @classmethod
    def get_test_name(cls) -> str:
        return "testfile2"

    @skip('Flaky on Windows and Mac')
    async def test_did_change_before_did_close(self) -> None:
        assert self.view
        self.view.window().run_command("chain", {
            "commands": [
                ["insert", {"characters": "TEST"}],
                ["save", {"async": False}],
                ["close", {}]
            ]
        })
        await self.await_message('textDocument/didChange')
        await self.await_message('textDocument/didSave')
        await self.await_message('textDocument/didClose')


class WillSaveWaitUntilTestCase(TextDocumentTestCase):

    @classmethod
    def get_test_server_capabilities(cls) -> dict:
        capabilities = deepcopy(super().get_test_server_capabilities())
        capabilities['capabilities']['textDocumentSync']['willSaveWaitUntil'] = True
        return capabilities

    async def test_will_save_wait_until(self) -> None:
        assert self.view
        self.insert_characters("A")
        await self.await_message("textDocument/didChange")
        await self.mock_response('textDocument/willSaveWaitUntil', [{
            'newText': "BBB",
            'range': {
                'start': {'line': 0, 'character': 0},
                'end': {'line': 0, 'character': 1}
            }
        }])
        self.view.settings().set("lsp_format_on_save", False)
        self.view.run_command("lsp_save", {'async': True})
        await self.await_message("textDocument/willSaveWaitUntil")
        await self.await_message("textDocument/didChange")
        await self.await_message("textDocument/didSave")
        text = self.view.substr(sublime.Region(0, self.view.size()))
        self.assertEqual("BBB", text)
        await self.await_clear_view_and_save()
