from LSP.plugin.hover import _test_contents
from LSP.plugin.core.url import filename_to_uri
from setup import TextDocumentTestCase, TIMEOUT_TIME, PERIOD_TIME, CI
import unittest
import sublime
import os

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

    @unittest.skipIf(sublime.platform() == "osx" and CI, "FIXME: This timeouts on OSX CI")
    def test_did_close(self) -> 'Generator':
        assert self.view
        self.view.set_scratch(True)
        self.view.close()
        self.view = None
        yield from self.await_message("textDocument/didClose")

    def test_did_change(self) -> 'Generator':
        assert self.view
        self.insert_characters("A")
        yield from self.await_message("textDocument/didChange")
        # multiple changes are batched into one didChange notification
        self.insert_characters("B")
        self.insert_characters("C")
        self.insert_characters("D")
        yield from self.await_message(("textDocument/didChange"))

    def test_sends_save_with_purge(self) -> 'Generator':
        assert self.view
        self.view.settings().set("lsp_format_on_save", False)
        self.insert_characters("A")
        self.view.run_command("save")
        yield from self.await_message("textDocument/didChange")
        yield from self.await_message("textDocument/didSave")
        yield from self.await_clear_view_and_save()

    @unittest.skip("FIXME: this blocks the test driver")
    def test_formats_on_save(self) -> 'Generator':
        assert self.view
        self.view.settings().set("lsp_format_on_save", True)
        self.insert_characters("A")
        yield from self.await_message("textDocument/didChange")
        self.set_response('textDocument/formatting', [{
            'newText': "BBB",
            'range': {
                'start': {'line': 0, 'character': 0},
                'end': {'line': 0, 'character': 3}
            }
        }])
        self.view.run_command("save")
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
        yield 100
        assert self.view
        self.insert_characters(GOTO_CONTENT)
        # Put the cursor back at the start of the buffer, otherwise is_at_word fails in goto.py.
        self.view.sel().clear()
        self.view.sel().add(sublime.Region(0, 0))
        method = 'textDocument/{}'.format(text_document_request)
        self.set_response(method, response)
        yield 100
        self.view.run_command('lsp_symbol_{}'.format(subl_command_suffix))
        yield 100
        yield from self.await_message(method)

        def condition() -> bool:
            nonlocal self
            assert self.view
            s = self.view.sel()
            if len(s) != 1:
                return False
            return s[0].begin() > 0

        yield {"condition": condition, "timeout": TIMEOUT_TIME, "period": PERIOD_TIME}
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


# class WillSaveWaitUntilTestCase(TextDocumentTestCase):

#     def get_test_server_capabilities(self) -> dict:
#         capabilities = deepcopy(super().get_test_server_capabilities())
#         capabilities['capabilities']['textDocumentSync']['willSaveWaitUntil'] = True
#         return capabilities

#     def test_will_save_wait_until(self) -> 'Generator':
#         assert self.view
#         self.insert_characters("A")
#         yield from self.await_message("textDocument/didChange")
#         self.set_response('textDocument/willSaveWaitUntil', [{
#             'newText': "BBB",
#             'range': {
#                 'start': {'line': 0, 'character': 0},
#                 'end': {'line': 0, 'character': 3}
#             }
#         }])
#         self.view.settings().set("lsp_format_on_save", False)
#         self.view.run_command("save")
#         yield from self.await_message("textDocument/willSaveWaitUntil")
#         yield from self.await_message("textDocument/didChange")
#         yield from self.await_message("textDocument/didSave")
#         text = self.view.substr(sublime.Region(0, self.view.size()))
#         self.assertEquals("BBB", text)
#         yield from self.await_clear_view_and_save()
