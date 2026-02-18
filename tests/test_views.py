from __future__ import annotations

from copy import deepcopy
from LSP.plugin.core.protocol import Point
from LSP.plugin.core.types import Any
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.core.views import did_change
from LSP.plugin.core.views import did_open
from LSP.plugin.core.views import did_save
from LSP.plugin.core.views import document_color_params
from LSP.plugin.core.views import format_diagnostic_for_html
from LSP.plugin.core.views import FORMAT_MARKED_STRING
from LSP.plugin.core.views import FORMAT_MARKUP_CONTENT
from LSP.plugin.core.views import FORMAT_STRING
from LSP.plugin.core.views import lsp_color_to_html
from LSP.plugin.core.views import lsp_color_to_phantom
from LSP.plugin.core.views import minihtml
from LSP.plugin.core.views import MissingUriError
from LSP.plugin.core.views import point_to_offset
from LSP.plugin.core.views import range_to_region
from LSP.plugin.core.views import selection_range_params
from LSP.plugin.core.views import text2html
from LSP.plugin.core.views import text_document_code_action_params
from LSP.plugin.core.views import text_document_formatting
from LSP.plugin.core.views import text_document_position_params
from LSP.plugin.core.views import text_document_range_formatting
from LSP.plugin.core.views import uri_from_view
from LSP.plugin.core.views import will_save
from LSP.plugin.core.views import will_save_wait_until
from LSP.protocol import CodeActionKind
from LSP.protocol import Diagnostic
from LSP.protocol import DiagnosticSeverity
from setup import make_stdio_test_config
from unittest.mock import MagicMock
from unittesting import DeferrableTestCase
import re
import sublime


class ViewsTest(DeferrableTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.view = sublime.active_window().new_file()  # new_file() always returns a ready view
        self.view.set_scratch(True)
        self.mock_file_name = "C:/Windows" if sublime.platform() == "windows" else "/etc"
        self.view.file_name = MagicMock(return_value=self.mock_file_name)
        self.view.run_command("insert", {"characters": "hello world\nfoo bar baz"})

    def tearDown(self) -> None:
        self.view.close()
        return super().tearDown()

    def test_missing_uri(self) -> None:
        self.view.settings().erase("lsp_uri")
        with self.assertRaises(MissingUriError):
            uri_from_view(self.view)

    def test_nonmissing_uri(self) -> None:

        class MockSettings:

            def get(value: str, default: Any) -> Any:
                return "file:///hello/there.txt"

        mock_settings = MockSettings()
        self.view.settings = MagicMock(return_value=mock_settings)
        uri = uri_from_view(self.view)
        self.assertEqual(uri, "file:///hello/there.txt")

    def test_did_open(self) -> None:
        self.view.settings().set("lsp_uri", filename_to_uri(self.mock_file_name))
        self.assertEqual(did_open(self.view, "python").params, {
            "textDocument": {
                "uri": filename_to_uri(self.mock_file_name),
                "languageId": "python",
                "text": "hello world\nfoo bar baz",
                "version": self.view.change_count()
            }
        })

    def test_did_change_full(self) -> None:
        version = self.view.change_count()
        self.view.settings().set("lsp_uri", filename_to_uri(self.mock_file_name))
        self.assertEqual(did_change(self.view, version).params, {
            "textDocument": {
                "uri": filename_to_uri(self.mock_file_name),
                "version": version
            },
            "contentChanges": [{"text": "hello world\nfoo bar baz"}]
        })

    def test_will_save(self) -> None:
        self.view.settings().set("lsp_uri", filename_to_uri(self.mock_file_name))
        self.assertEqual(will_save(filename_to_uri(self.mock_file_name), 42).params, {
            "textDocument": {"uri": filename_to_uri(self.mock_file_name)},
            "reason": 42
        })

    def test_will_save_wait_until(self) -> None:
        self.view.settings().set("lsp_uri", filename_to_uri(self.mock_file_name))
        self.assertEqual(will_save_wait_until(self.view, 1337).params, {
            "textDocument": {"uri": filename_to_uri(self.mock_file_name)},
            "reason": 1337
        })

    def test_did_save(self) -> None:
        self.view.settings().set("lsp_uri", filename_to_uri(self.mock_file_name))
        self.assertEqual(did_save(self.view, include_text=False).params, {
            "textDocument": {"uri": filename_to_uri(self.mock_file_name)}
        })
        self.assertEqual(did_save(self.view, include_text=True).params, {
            "textDocument": {"uri": filename_to_uri(self.mock_file_name)},
            "text": "hello world\nfoo bar baz"
        })

    def test_text_document_position_params(self) -> None:
        self.view.settings().set("lsp_uri", filename_to_uri(self.mock_file_name))
        self.assertEqual(text_document_position_params(self.view, 2), {
            "textDocument": {"uri": filename_to_uri(self.mock_file_name)},
            "position": {"line": 0, "character": 2}
        })

    def test_text_document_formatting(self) -> None:
        self.view.settings = MagicMock(return_value={
            "translate_tabs_to_spaces": False,
            "tab_size": 1234,
            "ensure_newline_at_eof_on_save": True,
            "lsp_uri": filename_to_uri(self.mock_file_name)
        })
        self.assertEqual(text_document_formatting(self.view).params, {
            "textDocument": {"uri": filename_to_uri(self.mock_file_name)},
            "options": {
                "tabSize": 1234,
                "insertSpaces": False,
                "trimTrailingWhitespace": False,
                "insertFinalNewline": True,
                "trimFinalNewlines": True
            }
        })

    def test_text_document_range_formatting(self) -> None:
        self.view.settings = MagicMock(return_value={
            "tab_size": 4321,
            "lsp_uri": filename_to_uri(self.mock_file_name)
        })
        self.assertEqual(text_document_range_formatting(self.view, sublime.Region(0, 2)).params, {
            "textDocument": {"uri": filename_to_uri(self.mock_file_name)},
            "options": {
                "tabSize": 4321,
                "insertSpaces": False,
                "trimTrailingWhitespace": False,
                "insertFinalNewline": False,
                "trimFinalNewlines": False
            },
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

    def test_selection_range_params(self) -> None:
        self.view.run_command("lsp_selection_set", {"regions": [(0, 5), (6, 11)]})
        self.view.settings().set("lsp_uri", filename_to_uri(self.mock_file_name))
        self.assertEqual(len(self.view.sel()), 2)
        self.assertEqual(self.view.substr(self.view.sel()[0]), "hello")
        self.assertEqual(self.view.substr(self.view.sel()[1]), "world")
        self.assertEqual(selection_range_params(self.view), {
            "textDocument": {"uri": filename_to_uri(self.mock_file_name)},
            "positions": [
                {"line": 0, "character": 5},
                {"line": 0, "character": 11}
            ]
        })

    def test_minihtml_no_allowed_formats(self) -> None:
        content = "<div>text\n</div>"
        with self.assertRaises(Exception):
            minihtml(self.view, content, allowed_formats=0)

    def test_minihtml_conflicting_formats(self) -> None:
        content = "<div>text\n</div>"
        with self.assertRaises(Exception):
            minihtml(self.view, content, allowed_formats=FORMAT_STRING | FORMAT_MARKED_STRING)

    def test_minihtml_format_string(self) -> None:
        content = "<div>text\n</div>"
        expect = "<p>&lt;div&gt;text<br>&lt;/div&gt;</p>"
        self.assertEqual(minihtml(self.view, content, allowed_formats=FORMAT_STRING), expect)

    def test_minihtml_format_marked_string(self) -> None:
        content = "<div>text\n</div>"
        expect = "<div>text\n</div>"
        self.assertEqual(minihtml(self.view, content, allowed_formats=FORMAT_MARKED_STRING), expect)

    def test_minihtml_format_markup_content(self) -> None:
        content = {'value': 'This is **bold** text', 'kind': 'markdown'}
        expect = "<p>This is <strong>bold</strong> text</p>"
        self.assertEqual(minihtml(self.view, content, allowed_formats=FORMAT_MARKUP_CONTENT), expect)

    def test_minihtml_handles_markup_content_plaintext(self) -> None:
        content = {'value': 'type TVec2i = specialize TGVec2<Integer>', 'kind': 'plaintext'}
        expect = "<p>type TVec2i = specialize TGVec2&lt;Integer&gt;</p>"
        allowed_formats = FORMAT_MARKED_STRING | FORMAT_MARKUP_CONTENT
        self.assertEqual(minihtml(self.view, content, allowed_formats=allowed_formats), expect)

    def test_minihtml_handles_marked_string(self) -> None:
        content = {'value': 'import json', 'language': 'python'}
        expect = '<div class="highlight"><pre><span>import</span><span> </span><span>json</span><br></pre></div>'
        allowed_formats = FORMAT_MARKED_STRING | FORMAT_MARKUP_CONTENT
        formatted = self._strip_style_attributes(minihtml(self.view, content, allowed_formats=allowed_formats))
        self.assertEqual(formatted, expect)

    def test_minihtml_handles_marked_string_mutiple_spaces(self) -> None:
        content = {'value': 'import  json', 'language': 'python'}
        expect = '<div class="highlight"><pre><span>import</span><span>&nbsp; </span><span>json</span><br></pre></div>'
        allowed_formats = FORMAT_MARKED_STRING | FORMAT_MARKUP_CONTENT
        formatted = self._strip_style_attributes(minihtml(self.view, content, allowed_formats=allowed_formats))
        self.assertEqual(formatted, expect)

    def test_minihtml_handles_marked_string_array(self) -> None:
        content = [
            {'value': 'import sys', 'language': 'python'},
            {'value': 'let x', 'language': 'js'}
        ]
        expect = '\n\n'.join([
            '<div class="highlight"><pre><span>import</span><span> </span><span>sys</span><br></pre></div>',
            '<div class="highlight"><pre><span>let</span><span> </span><span>x</span><br></pre></div>'
        ])
        allowed_formats = FORMAT_MARKED_STRING | FORMAT_MARKUP_CONTENT
        formatted = self._strip_style_attributes(minihtml(self.view, content, allowed_formats=allowed_formats))
        self.assertEqual(formatted, expect)

    def test_minihtml_ignores_non_allowed_string(self) -> None:
        content = "<div>text\n</div>"
        expect = ""
        self.assertEqual(minihtml(self.view, content, allowed_formats=FORMAT_MARKUP_CONTENT), expect)

    def test_minihtml_ignores_non_allowed_marked_string(self) -> None:
        content = {'value': 'import sys', 'language': 'python'}
        expect = ""
        self.assertEqual(minihtml(self.view, content, allowed_formats=FORMAT_MARKUP_CONTENT), expect)

    def test_minihtml_ignores_non_allowed_marked_string_array(self) -> None:
        content = ["a", "b"]
        expect = ""
        self.assertEqual(minihtml(self.view, content, allowed_formats=FORMAT_MARKUP_CONTENT), expect)

    def test_minihtml_ignores_non_allowed_markup_content(self) -> None:
        content = {'value': 'a<span>b</span>', 'kind': 'plaintext'}
        expect = ""
        self.assertEqual(minihtml(self.view, content, allowed_formats=FORMAT_STRING), expect)

    def test_minihtml_magiclinks(self) -> None:
        content = {'value': 'https://github.com/sublimelsp/LSP', 'kind': 'markdown'}
        expect_attributes = [
            'class="magiclink magiclink-github magiclink-repository"',
            'href="https://github.com/sublimelsp/LSP"',
            'title="GitHub Repository: sublimelsp/LSP"'
        ]
        expect = '<p><a {}>sublimelsp/LSP</a></p>'.format(' '.join(expect_attributes))
        self.assertEqual(minihtml(self.view, content, allowed_formats=FORMAT_MARKUP_CONTENT), expect)

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

    def test_lsp_color_to_phantom(self) -> None:
        response = [
            {
                "color": {
                    "green": 0.9725490196078431,
                    "blue": 1,
                    "red": 0.9411764705882353,
                    "alpha": 1
                },
                "range": {
                    "start": {
                        "character": 0,
                        "line": 0
                    },
                    "end": {
                        "character": 5,
                        "line": 0
                    }
                }
            }
        ]
        phantom = lsp_color_to_phantom(self.view, response[0])
        self.assertEqual(phantom.content, lsp_color_to_html(response[0]))
        self.assertEqual(phantom.region, range_to_region(response[0]["range"], self.view))

    def test_document_color_params(self) -> None:
        self.view.settings().set("lsp_uri", filename_to_uri(self.mock_file_name))
        self.assertEqual(
            document_color_params(self.view),
            {"textDocument": {"uri": filename_to_uri(self.mock_file_name)}})

    def test_text_document_code_action_params(self) -> None:
        self.view.settings().set("lsp_uri", filename_to_uri(self.mock_file_name))
        diagnostic: Diagnostic = {
            "message": "oops",
            "severity": DiagnosticSeverity.Error,
            "range": {
                "start": {
                    "character": 0,
                    "line": 0
                },
                "end": {
                    "character": 1,
                    "line": 0
                }
            }
        }
        self.view.run_command("append", {"characters": "a b c\n"})
        params = text_document_code_action_params(
            view=self.view,
            region=sublime.Region(0, 1),
            diagnostics=[diagnostic],
            only_kinds=[CodeActionKind.Refactor]
        )
        self.assertEqual(params["textDocument"], {"uri": filename_to_uri(self.mock_file_name)})

    def test_format_diagnostic_for_html(self) -> None:
        diagnostic1: Diagnostic = {
            "message": "oops",
            "severity": DiagnosticSeverity.Error,
            # The relatedInformation is present here, but it's an empty list.
            # This should have the same behavior as having no relatedInformation present.
            "relatedInformation": [],
            "range": {
                "start": {
                    "character": 0,
                    "line": 0
                },
                "end": {
                    "character": 5,
                    "line": 0
                }
            }
        }
        # Make the same diagnostic but without the relatedInformation
        diagnostic2 = deepcopy(diagnostic1)
        diagnostic2.pop("relatedInformation")
        self.assertIn("relatedInformation", diagnostic1)
        self.assertNotIn("relatedInformation", diagnostic2)
        client_config = make_stdio_test_config()
        # They should result in the same minihtml.
        self.assertEqual(
            format_diagnostic_for_html(client_config, diagnostic1, "/foo/bar"),
            format_diagnostic_for_html(client_config, diagnostic2, "/foo/bar")
        )

    def test_escaped_newline_in_markdown(self) -> None:
        self.assertEqual(
            minihtml(self.view, {"kind": "markdown", "value": "hello\\\nworld"}, FORMAT_MARKUP_CONTENT),
            "<p>hello\\\nworld</p>"
        )

    def test_single_backslash_in_markdown(self) -> None:
        self.assertEqual(
            minihtml(self.view, {"kind": "markdown", "value": "A\\B"}, FORMAT_MARKUP_CONTENT),
            "<p>A\\B</p>"
        )
