from copy import deepcopy
from LSP.plugin import Request
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.core.views import entire_content
from LSP.plugin.hover import _test_contents
from setup import TextDocumentTestCase
from setup import TIMEOUT_TIME
from setup import YieldPromise
import os
import sublime

try:
    from typing import Generator, Optional, Iterable, Tuple, List
    assert Generator and Optional and Iterable and Tuple and List
except ImportError:
    pass

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

    def test_did_open(self) -> 'Generator':
        # Just the existence of this method checks "initialize" -> "initialized" -> "textDocument/didOpen"
        # -> "shutdown" -> client shut down
        pass

    def test_out_of_bounds_column_for_text_document_edit(self) -> 'Generator':
        self.insert_characters("a\nb\nc\n")
        self.view.run_command("lsp_apply_document_edit", {"changes": [
            (
                (1, 0),  # start row-col
                (1, 10000),  # end row-col (the col offset is out of bounds intentionally)
                "hello there",  # new text
                None  # version
            )
        ]})
        self.assertEqual(entire_content(self.view), "a\nhello there\nc\n")

    def test_did_close(self) -> 'Generator':
        self.assertTrue(self.view)
        self.assertTrue(self.view.is_valid())
        self.view.close()
        yield from self.await_message("textDocument/didClose")

    def test_did_change(self) -> 'Generator':
        assert self.view
        self.maxDiff = None
        self.insert_characters("A")
        yield from self.await_message("textDocument/didChange")
        # multiple changes are batched into one didChange notification
        self.insert_characters("B\n")
        self.insert_characters("🙂\n")
        self.insert_characters("D")
        promise = YieldPromise()
        yield from self.await_message("textDocument/didChange", promise)
        self.assertEqual(promise.result(), {
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

    def test_sends_save_with_purge(self) -> 'Generator':
        assert self.view
        self.view.settings().set("lsp_format_on_save", False)
        self.insert_characters("A")
        self.view.run_command("lsp_save")
        yield from self.await_message("textDocument/didChange")
        yield from self.await_message("textDocument/didSave")
        yield from self.await_clear_view_and_save()

    def test_formats_on_save(self) -> 'Generator':
        assert self.view
        self.view.settings().set("lsp_format_on_save", True)
        self.insert_characters("A")
        yield from self.await_message("textDocument/didChange")
        self.set_response('textDocument/formatting', [{
            'newText': "BBB",
            'range': {
                'start': {'line': 0, 'character': 0},
                'end': {'line': 0, 'character': 1}
            }
        }])
        self.view.run_command("lsp_save")
        yield from self.await_message("textDocument/formatting")
        yield from self.await_message("textDocument/didChange")
        yield from self.await_message("textDocument/didSave")
        text = self.view.substr(sublime.Region(0, self.view.size()))
        self.assertEquals("BBB", text)
        yield from self.await_clear_view_and_save()

    def test_hover_info(self) -> 'Generator':
        assert self.view
        self.set_response('textDocument/hover', {"contents": "greeting"})
        self.view.run_command('insert', {"characters": "Hello Wrld"})
        self.assertFalse(self.view.is_popup_visible())
        self.view.run_command('lsp_hover', {'point': 3})
        yield lambda: self.view.is_popup_visible()
        last_content = _test_contents[-1]
        self.assertTrue("greeting" in last_content)

    def test_remove_line_and_then_insert_at_that_line_at_end(self) -> 'Generator':
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
        yield from self.__run_formatting_test(original, expected, file_changes)

    def test_apply_formatting(self) -> 'Generator':
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
        yield from self.__run_formatting_test(original, expected, file_changes)

    def test_apply_formatting_and_preserve_order(self) -> 'Generator':
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
        yield from self.__run_formatting_test(original, expected, file_changes)

    def test_tabs_are_respected_even_when_translate_tabs_to_spaces_is_set_to_true(self) -> 'Generator':
        original = ' ' * 4
        file_changes = [((0, 0), (0, 4), '\t')]
        expected = '\t'
        assert self.view
        self.view.settings().set("translate_tabs_to_spaces", True)
        yield from self.__run_formatting_test(original, expected, file_changes)
        # Make sure the user's settings haven't changed
        self.assertTrue(self.view.settings().get("translate_tabs_to_spaces"))

    def __run_formatting_test(
        self,
        original: 'Iterable[str]',
        expected: 'Iterable[str]',
        file_changes: 'List[Tuple[Tuple[int, int], Tuple[int, int], str]]'
    ) -> 'Generator':
        assert self.view
        original_change_count = self.insert_characters(''.join(original))
        # self.assertEqual(original_change_count, 1)
        self.set_response('textDocument/formatting', [{
            'newText': new_text,
            'range': {
                'start': {'line': start[0], 'character': start[1]},
                'end': {'line': end[0], 'character': end[1]}}} for start, end, new_text in file_changes])
        self.view.run_command('lsp_format_document')
        yield from self.await_message('textDocument/formatting')
        yield from self.await_view_change(original_change_count + len(file_changes))
        edited_content = self.view.substr(sublime.Region(0, self.view.size()))
        self.assertEquals(edited_content, ''.join(expected))

    def __run_goto_test(self, response: list, text_document_request: str, subl_command_suffix: str) -> 'Generator':
        assert self.view
        self.insert_characters(GOTO_CONTENT)
        # Put the cursor back at the start of the buffer, otherwise is_at_word fails in goto.py.
        self.view.sel().clear()
        self.view.sel().add(sublime.Region(0, 0))
        method = 'textDocument/{}'.format(text_document_request)
        self.set_response(method, response)
        self.view.run_command('lsp_symbol_{}'.format(subl_command_suffix))
        yield from self.await_message(method)

        def condition() -> bool:
            nonlocal self
            assert self.view
            s = self.view.sel()
            if len(s) != 1:
                return False
            return s[0].begin() > 0

        yield {"condition": condition, "timeout": TIMEOUT_TIME}
        first = self.view.sel()[0].begin()
        self.assertEqual(self.view.substr(sublime.Region(first, first + 1)), "F")

    def test_definition(self) -> 'Generator':
        yield from self.__run_goto_test(GOTO_RESPONSE, 'definition', 'definition')

    def test_definition_location_link(self) -> 'Generator':
        yield from self.__run_goto_test(GOTO_RESPONSE_LOCATION_LINK, 'definition', 'definition')

    def test_type_definition(self) -> 'Generator':
        yield from self.__run_goto_test(GOTO_RESPONSE, 'typeDefinition', 'type_definition')

    def test_type_definition_location_link(self) -> 'Generator':
        yield from self.__run_goto_test(GOTO_RESPONSE_LOCATION_LINK, 'typeDefinition', 'type_definition')

    def test_declaration(self) -> 'Generator':
        yield from self.__run_goto_test(GOTO_RESPONSE, 'declaration', 'declaration')

    def test_declaration_location_link(self) -> 'Generator':
        yield from self.__run_goto_test(GOTO_RESPONSE_LOCATION_LINK, 'declaration', 'declaration')

    def test_implementation(self) -> 'Generator':
        yield from self.__run_goto_test(GOTO_RESPONSE, 'implementation', 'implementation')

    def test_implementation_location_link(self) -> 'Generator':
        yield from self.__run_goto_test(GOTO_RESPONSE_LOCATION_LINK, 'implementation', 'implementation')

    def test_expand_selection(self) -> 'Generator':
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

        def expand_and_check(a: int, b: int) -> 'Generator':
            self.set_response("textDocument/selectionRange", response)
            self.view.run_command("lsp_expand_selection")
            yield from self.await_message("textDocument/selectionRange")
            yield lambda: self.view.sel()[0] == sublime.Region(a, b)

        yield from expand_and_check(2, 3)
        yield from expand_and_check(1, 3)
        yield from expand_and_check(0, 5)

    def test_rename(self) -> 'Generator':
        self.insert_characters("foo\nfoo\nfoo\n")
        self.set_response("textDocument/rename", {
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
                            'range': {'start': {'character': 0, 'line': 2}, 'end': {'character': 3, 'line': 2}},
                            'newText': 'bar'
                        }
                    ]
                }
            }
        )
        self.view.run_command("lsp_selection_set", {"regions": [(0, 0)]})
        self.view.run_command("lsp_symbol_rename", {"new_name": "bar"})
        yield from self.await_message("textDocument/rename")
        yield from self.await_view_change(9)
        self.assertEqual(self.view.substr(sublime.Region(0, self.view.size())), "bar\nbar\nbar\n")

    def test_run_command(self) -> 'Generator':
        self.set_response("workspace/executeCommand", {"canReturnAnythingHere": "asdf"})
        promise = YieldPromise()
        sublime.set_timeout_async(
            lambda: self.session.execute_command(
                {"command": "foo", "arguments": ["hello", "there", "general", "kenobi"]},
                progress=False
            ).then(promise.fulfill)
        )
        yield from self.await_promise(promise)
        yield from self.await_message("workspace/executeCommand")
        self.assertEqual(promise.result(), {"canReturnAnythingHere": "asdf"})

    def test_progress(self) -> 'Generator':
        request = Request("foobar", {"hello": "world"}, self.view, progress=True)
        self.set_response("foobar", {"general": "kenobi"})
        promise = self.session.send_request_task(request)
        yield lambda: "workDoneToken" in request.params
        result = yield from self.await_promise(promise)
        self.assertEqual(result, {"general": "kenobi"})


class WillSaveWaitUntilTestCase(TextDocumentTestCase):

    @classmethod
    def get_test_server_capabilities(cls) -> dict:
        capabilities = deepcopy(super().get_test_server_capabilities())
        capabilities['capabilities']['textDocumentSync']['willSaveWaitUntil'] = True
        return capabilities

    def test_will_save_wait_until(self) -> 'Generator':
        assert self.view
        self.insert_characters("A")
        yield from self.await_message("textDocument/didChange")
        self.set_response('textDocument/willSaveWaitUntil', [{
            'newText': "BBB",
            'range': {
                'start': {'line': 0, 'character': 0},
                'end': {'line': 0, 'character': 1}
            }
        }])
        self.view.settings().set("lsp_format_on_save", False)
        self.view.run_command("lsp_save")
        yield from self.await_message("textDocument/willSaveWaitUntil")
        yield from self.await_message("textDocument/didChange")
        yield from self.await_message("textDocument/didSave")
        text = self.view.substr(sublime.Region(0, self.view.size()))
        self.assertEquals("BBB", text)
        yield from self.await_clear_view_and_save()
