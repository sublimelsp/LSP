from __future__ import annotations

from LSP.plugin.core.url import filename_to_uri
from LSP.plugin.core.url import parse_uri
from LSP.plugin.core.url import view_to_uri
import os
import sublime
import sys
import unittest
import unittest.mock


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

    def test_unc_path(self):
        scheme, path = parse_uri('file://192.168.80.2/D%24/www/File.php')
        self.assertEqual(scheme, "file")
        self.assertEqual(path, R'\\192.168.80.2\D$\www\File.php')

    def test_wsl_path(self):
        scheme, path = parse_uri('file://wsl%24/Ubuntu-20.04/File.php')
        self.assertEqual(scheme, "file")
        self.assertEqual(path, R'\\wsl$\Ubuntu-20.04\File.php')


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
        self.assertEqual(uri, "res:/Packages/Package%20Control/dir/file.py")

    def test_buffer_uri(self):
        view = sublime.active_window().active_view()
        assert view
        view.file_name = unittest.mock.MagicMock(return_value=None)
        view.buffer_id = unittest.mock.MagicMock(return_value=42)
        uri = view_to_uri(view)
        self.assertEqual(uri, "buffer:42")

    def test_parse_uri(self):
        scheme, _ = parse_uri("buffer:42")
        self.assertEqual(scheme, "buffer")
        scheme, _ = parse_uri("www.example.com/foo:bar")
        self.assertEqual(scheme, "")
