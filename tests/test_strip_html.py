import unittest
from LSP.plugin.core.strip_html import strip_html


class StripHtmlTest(unittest.TestCase):
    def test_strip_html(self):
        result = strip_html("<p>Hello <b>world</b><span id='hello'>!</span></p>")
        expected = "Hello world!"
        self.assertEqual(result, expected)
