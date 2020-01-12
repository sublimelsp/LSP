from LSP.plugin.core.url import (filename_to_uri, uri_to_filename)
import sys
import unittest


class WindowsTests(unittest.TestCase):

    @unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
    def test_converts_path_to_uri(self):
        self.assertEqual("file:///C:/dir%20ectory/file.txt", filename_to_uri("c:\\dir ectory\\file.txt"))

    @unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
    def test_converts_uri_to_path(self):
        self.assertEqual("C:\\dir ectory\\file.txt", uri_to_filename("file:///c:/dir ectory/file.txt"))

    @unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
    def test_converts_encoded_bad_drive_uri_to_path(self):
        # url2pathname does not understand %3A
        self.assertEqual("c:\\dir ectory\\file.txt", uri_to_filename("file:///c%3A/dir%20ectory/file.txt"))


class NixTests(unittest.TestCase):

    @unittest.skipIf(sys.platform.startswith("win"), "requires non-Windows")
    def test_converts_path_to_uri(self):
        self.assertEqual("file:///dir%20ectory/file.txt", filename_to_uri("/dir ectory/file.txt"))

    @unittest.skipIf(sys.platform.startswith("win"), "requires non-Windows")
    def test_converts_uri_to_path(self):
        self.assertEqual("/dir ectory/file.txt", uri_to_filename("file:///dir ectory/file.txt"))
