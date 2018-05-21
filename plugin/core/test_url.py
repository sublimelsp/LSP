from .url import (filename_to_uri, uri_to_filename)
import sys
import unittest


class WindowsTests(unittest.TestCase):

    @unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
    def test_converts_path_to_uri(self):
        self.assertEqual("file:///C:/dir%20ectory/file.txt", filename_to_uri("c:\\dir ectory\\file.txt"))

    @unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
    def test_converts_uri_to_path(self):
        self.assertEqual("C:\\dir ectory\\file.txt", uri_to_filename("file:///c:/dir ectory/file.txt"))
