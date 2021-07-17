from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.core.url import parse_uri
from LSP.plugin.core.url import view_to_uri
import sys
import unittest
import unittest.mock
import sublime
import os


@unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
class WindowsTests(unittest.TestCase):

    def test_converts_path_to_uri(self):
        self.assertEqual("file:///C:/dir%20ectory/file.txt", filename_to_uri("c:\\dir ectory\\file.txt"))

    def test_converts_uri_to_path(self):
        self.assertEqual("C:\\dir ectory\\file.txt", parse_uri("file:///c:/dir ectory/file.txt")[1])

    def test_converts_encoded_bad_drive_uri_to_path(self):
        # url2pathname does not understand %3A
        self.assertEqual("C:\\dir ectory\\file.txt", parse_uri("file:///c%3A/dir%20ectory/file.txt")[1])

    def test_view_to_uri_with_valid_filename(self):
        view = sublime.active_window().active_view()
        assert view
        view.file_name = unittest.mock.MagicMock(
            return_value="C:\\Users\\A b\\popups.css"
        )
        uri = view_to_uri(view)
        self.assertEqual(uri, "file:///C:/Users/A%20b/popups.css")


@unittest.skipIf(sys.platform.startswith("win"), "requires non-Windows")
class NixTests(unittest.TestCase):

    def test_converts_path_to_uri(self):
        self.assertEqual("file:///dir%20ectory/file.txt", filename_to_uri("/dir ectory/file.txt"))

    def test_converts_uri_to_path(self):
        self.assertEqual("/dir ectory/file.txt", parse_uri("file:///dir ectory/file.txt")[1])

    def test_view_to_uri_with_valid_filename(self):
        view = sublime.active_window().active_view()
        assert view
        view.file_name = unittest.mock.MagicMock(return_value="/foo/bar/baz.txt")
        uri = view_to_uri(view)
        self.assertEqual(uri, "file:///foo/bar/baz.txt")


class MultiplatformTests(unittest.TestCase):

    def test_resource_path(self):
        uri = filename_to_uri(os.path.join(sublime.installed_packages_path(), "Package Control", "dir", "file.py"))
        self.assertEqual(uri, "res://Packages/Package%20Control/dir/file.py")

    def test_buffer_uri(self):
        view = sublime.active_window().active_view()
        assert view
        view.file_name = unittest.mock.MagicMock(return_value=None)
        view.buffer_id = unittest.mock.MagicMock(return_value=42)
        uri = view_to_uri(view)
        self.assertEqual(uri, "buffer://sublime/42")
