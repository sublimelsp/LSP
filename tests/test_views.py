from LSP.plugin.core.protocol import Point
from LSP.plugin.core.typing import Generator
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.core.views import did_change
from LSP.plugin.core.views import did_open
from LSP.plugin.core.views import did_save
from LSP.plugin.core.views import MissingFilenameError
from LSP.plugin.core.views import minihtml
from LSP.plugin.core.views import point_to_offset
from LSP.plugin.core.views import text2html
from LSP.plugin.core.views import text_document_formatting
from LSP.plugin.core.views import text_document_position_params
from LSP.plugin.core.views import text_document_range_formatting
from LSP.plugin.core.views import uri_from_view
from LSP.plugin.core.views import will_save
from LSP.plugin.core.views import will_save_wait_until
from unittest.mock import MagicMock
from unittesting import DeferrableTestCase
import re
import sublime


class ViewsTest(DeferrableTestCase):

    def setUp(self) -> Generator:
        super().setUp()
        self.view = sublime.active_window().new_file()
        yield not self.view.is_loading()
        self.view.set_scratch(True)
        self.mock_file_name = "C:/Windows" if sublime.platform() == "windows" else "/etc"
        self.view.file_name = MagicMock(return_value=self.mock_file_name)
        self.view.run_command("insert", {"characters": "hello world\nfoo bar baz"})

    def tearDown(self) -> None:
        self.view.close()
        return super().tearDown()

    def test_missing_filename(self) -> None:
        self.view.file_name = MagicMock(return_value=None)
        with self.assertRaises(MissingFilenameError):
            uri_from_view(self.view)

    def test_did_open(self) -> None:
        self.assertEqual(did_open(self.view, "python").params, {
            "textDocument": {
                "uri": filename_to_uri(self.mock_file_name),
                "languageId": "python",
                "text": "hello world\nfoo bar baz",
                "version": self.view.change_count()
            }
        })

    def test_did_change_full(self) -> None:
        self.assertEqual(did_change(self.view).params, {
            "textDocument": {
                "uri": filename_to_uri(self.mock_file_name),
                "version": self.view.change_count()
            },
            "contentChanges": [{"text": "hello world\nfoo bar baz"}]
        })

    def test_will_save(self) -> None:
        self.assertEqual(will_save(self.view, 42).params, {
            "textDocument": {"uri": filename_to_uri(self.mock_file_name)},
            "reason": 42
        })

    def test_will_save_wait_until(self) -> None:
        self.assertEqual(will_save_wait_until(self.view, 1337).params, {
            "textDocument": {"uri": filename_to_uri(self.mock_file_name)},
            "reason": 1337
        })

    def test_did_save(self) -> None:
        self.assertEqual(did_save(self.view, include_text=False).params, {
            "textDocument": {"uri": filename_to_uri(self.mock_file_name)}
        })
        self.assertEqual(did_save(self.view, include_text=True).params, {
            "textDocument": {"uri": filename_to_uri(self.mock_file_name)},
            "text": "hello world\nfoo bar baz"
        })

    def test_text_document_position_params(self) -> None:
        self.assertEqual(text_document_position_params(self.view, 2), {
            "textDocument": {"uri": filename_to_uri(self.mock_file_name)},
            "position": {"line": 0, "character": 2}
        })

    def test_text_document_formatting(self) -> None:
        self.view.settings = MagicMock(return_value={"translate_tabs_to_spaces": False, "tab_size": 1234})
        self.assertEqual(text_document_formatting(self.view).params, {
            "textDocument": {"uri": filename_to_uri(self.mock_file_name)},
            "options": {"tabSize": 1234, "insertSpaces": False}
        })

    def test_text_document_range_formatting(self) -> None:
        self.view.settings = MagicMock(return_value={"tab_size": 4321})
        self.assertEqual(text_document_range_formatting(self.view, sublime.Region(0, 2)).params, {
            "textDocument": {"uri": filename_to_uri(self.mock_file_name)},
            "options": {"tabSize": 4321, "insertSpaces": False},
            "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 2}}
        })

    def test_point_to_offset(self) -> None:
        first_line_length = len(self.view.line(0))
        self.assertEqual(point_to_offset(Point(1, 2), self.view), first_line_length + 3)
        self.assertEqual(point_to_offset(Point(0, first_line_length + 9999), self.view), first_line_length)

    def test_point_to_offset_utf16(self) -> None:
        self.view.run_command("insert", {"characters": "🍺foo"})
        foobarbaz_length = len("foo bar baz")
        offset = point_to_offset(Point(1, foobarbaz_length), self.view)
        # Sanity check
        self.assertEqual(self.view.substr(offset), "🍺")
        # When we move two UTF-16 points further, we should encompass the beer emoji.
        # So that means that the code point offsets should have a difference of 1.
        self.assertEqual(point_to_offset(Point(1, foobarbaz_length + 2), self.view) - offset, 1)

    def test_minihtml_prefers_plaintext(self) -> None:
        content = "<div>text\n</div>"
        expect = "&lt;div&gt;text<br>&lt;/div&gt;"
        self.assertEqual(minihtml(self.view, content, prefer_plain_text=True), expect)

    def test_minihtml_prefers_markdown(self) -> None:
        content = "<div>text\n</div>"
        expect = "<div>text</div>"
        self.assertEqual(minihtml(self.view, content, prefer_plain_text=False), expect)

    def test_minihtml_handles_markup_content_plaintext(self) -> None:
        content = {'value': 'type TVec2i = specialize TGVec2<Integer>', 'kind': 'plaintext'}
        expect = "type TVec2i = specialize TGVec2&lt;Integer&gt;"
        self.assertEqual(minihtml(self.view, content, prefer_plain_text=True), expect)

    def test_minihtml_handles_markup_content_markdown(self) -> None:
        content = {'value': 'This is **bold** text', 'kind': 'markdown'}
        expect = "<p>This is <strong>bold</strong> text</p>"
        self.assertEqual(minihtml(self.view, content, prefer_plain_text=True), expect)

    def test_minihtml_handles_marked_content(self) -> None:
        content = {'value': 'import json', 'language': 'python'}
        expect = '<div class="highlight"><pre><span>import</span><span> </span><span>json</span><br></pre></div>'
        formatted = minihtml(self.view, content, prefer_plain_text=True)
        self.assertEqual(self._strip_style_attributes(formatted), expect)

    def test_minihtml_handles_marked_content_mutiple_spaces(self) -> None:
        content = {'value': 'import  json', 'language': 'python'}
        expect = '<div class="highlight"><pre><span>import</span><span>&nbsp; </span><span>json</span><br></pre></div>'
        formatted = minihtml(self.view, content, prefer_plain_text=True)
        self.assertEqual(self._strip_style_attributes(formatted), expect)

    def test_minihtml_handles_marked_content_array(self) -> None:
        content = [
            {'value': 'import sys', 'language': 'python'},
            {'value': 'let x', 'language': 'js'}
        ]
        expect = ''.join([
            '<div class="highlight"><pre><span>import</span><span> </span><span>sys</span><br></pre></div>'
            '<div class="highlight"><pre><span>let</span><span> </span><span>x</span><br></pre></div>'
        ])
        formatted = minihtml(self.view, content, prefer_plain_text=True)
        self.assertEqual(self._strip_style_attributes(formatted), expect)

    def _strip_style_attributes(self, content: str) -> str:
        return re.sub(r'\s+style="[^"]+"', '', content)

    def test_text2html_replaces_tabs_with_br(self) -> None:
        self.assertEqual(text2html("Hello,\t world "), "Hello,&nbsp;&nbsp;&nbsp;&nbsp; world ")

    def test_text2html_non_breaking_space_and_control_char_with_entity(self) -> None:
        self.assertEqual(text2html("no\xc2\xa0breaks"), "no&nbsp;&nbsp;breaks")

    def test_text2html_replaces_two_or_more_spaces_with_nbsp(self) -> None:
        content = " One  Two   Three One    Four"
        expect = " One&nbsp;&nbsp;Two&nbsp;&nbsp;&nbsp;Three One&nbsp;&nbsp;&nbsp;&nbsp;Four"
        self.assertEqual(text2html(content), expect)

    def test_text2html_does_not_replace_one_space_with_nbsp(self) -> None:
        content = " John has one apple "
        self.assertEqual(text2html(content), content)

    def test_text2html_replaces_newlines_with_br(self) -> None:
        self.assertEqual(text2html("a\nb"), "a<br>b")

    def test_text2html_parses_link_simple(self) -> None:
        content = "https://github.com/sublimelsp/LSP"
        expect = "<a href='https://github.com/sublimelsp/LSP'>https://github.com/sublimelsp/LSP</a>"
        self.assertEqual(text2html(content), expect)

    def test_text2html_parses_link_in_angle_brackets(self) -> None:
        content = "<https://github.com/sublimelsp/LSP>"
        expect = "&lt;<a href='https://github.com/sublimelsp/LSP'>https://github.com/sublimelsp/LSP</a>&gt;"
        self.assertEqual(text2html(content), expect)

    def test_text2html_parses_link_in_double_quotes(self) -> None:
        content = "\"https://github.com/sublimelsp/LSP\""
        expect = "\"<a href='https://github.com/sublimelsp/LSP'>https://github.com/sublimelsp/LSP</a>\""
        self.assertEqual(text2html(content), expect)

    def test_text2html_parses_link_in_single_quotes(self) -> None:
        content = "'https://github.com/sublimelsp/LSP'"
        expect = "'<a href='https://github.com/sublimelsp/LSP'>https://github.com/sublimelsp/LSP</a>'"
        self.assertEqual(text2html(content), expect)
