from LSP.plugin.core.protocol import Point
from LSP.plugin.core.typing import Generator
from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.core.views import did_change
from LSP.plugin.core.views import did_open
from LSP.plugin.core.views import did_save
from LSP.plugin.core.views import MissingFilenameError
from LSP.plugin.core.views import point_to_offset
from LSP.plugin.core.views import text_document_formatting
from LSP.plugin.core.views import text_document_position_params
from LSP.plugin.core.views import text_document_range_formatting
from LSP.plugin.core.views import uri_from_view
from LSP.plugin.core.views import will_save
from LSP.plugin.core.views import will_save_wait_until
from unittest.mock import MagicMock
from unittesting import DeferrableTestCase
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
        # TODO: See comment in point_to_offset function
        # self.assertEqual(point_to_offset(Point(0, first_line_length + 9999), self.view), first_line_length)

    def test_point_to_offset_utf16(self) -> None:
        self.view.run_command("insert", {"characters": "🍺foo"})
        foobarbaz_length = len("foo bar baz")
        offset = point_to_offset(Point(1, foobarbaz_length), self.view)
        # Sanity check
        self.assertEqual(self.view.substr(offset), "🍺")
        # When we move two UTF-16 points further, we should encompass the beer emoji.
        # So that means that the code point offsets should have a difference of 1.
        self.assertEqual(point_to_offset(Point(1, foobarbaz_length + 2), self.view) - offset, 1)
