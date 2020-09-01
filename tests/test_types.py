from LSP.plugin.core.types import diff
from LSP.plugin.core.types import DocumentSelector
from LSP.plugin.core.typing import List
from unittest.mock import MagicMock
import sublime
import unittest


class TestDiff(unittest.TestCase):

    def test_add(self) -> None:
        added, removed = diff(("a", "b", "c"), ("a", "b", "c", "d"))
        self.assertEqual(added, set(("d",)))
        self.assertFalse(removed)

    def test_remove(self) -> None:
        added, removed = diff(("a", "b", "c"), ("c", "b"))
        self.assertFalse(added)
        self.assertEqual(removed, set(("a",)))

    def test_add_and_remove(self) -> None:
        added, removed = diff(("a", "b", "c"), ("c", "d"))
        self.assertEqual(added, set(("d",)))
        self.assertEqual(removed, set(("a", "b")))

    def test_with_sets(self) -> None:
        added, removed = diff(set(("a", "b", "c")), ("x", "y", "z"))
        self.assertEqual(added, set(("x", "y", "z")))
        self.assertEqual(removed, set(("a", "b", "c")))

    def test_with_more_sets(self) -> None:
        added, removed = diff(set(("a", "b")), set(("b", "c")))
        self.assertEqual(added, set(("c",)))
        self.assertEqual(removed, set(("a",)))

    def test_completely_new(self) -> None:
        new = {"ocaml", "polymer-ide", "elixir-ls", "jdtls", "dart", "reason", "golsp", "clangd", "pwsh", "vhdl_ls"}
        added, removed = diff(set(), new)
        self.assertEqual(added, new)
        self.assertFalse(removed)


class TestDocumentSelector(unittest.TestCase):

    def setUp(self) -> None:
        self._opened_views = []  # type: List[sublime.View]

    def tearDown(self) -> None:
        for view in self._opened_views:
            view.close()
        self._opened_views.clear()

    def _make_view(self, syntax: str, file_name: str) -> sublime.View:
        view = sublime.active_window().new_file(0, syntax)
        self._opened_views.append(view)
        view.set_scratch(True)
        self.assertFalse(view.is_loading())
        view.file_name = MagicMock(return_value=file_name)
        return view

    def test_language(self) -> None:
        selector = DocumentSelector([{"language": "txt"}])
        view = self._make_view("Packages/Text/Plain text.tmLanguage", "foobar.txt")
        self.assertTrue(selector.matches(view))
        view = self._make_view("Packages/Python/Python.sublime-syntax", "hello.py")
        self.assertFalse(selector.matches(view))

    def test_pattern_basics(self) -> None:
        selector = DocumentSelector([{"language": "html", "pattern": "**/*.component.html"}])
        view = self._make_view("Packages/HTML/HTML.sublime-syntax", "index.html")
        self.assertFalse(selector.matches(view))
        view = self._make_view("Packages/HTML/HTML.sublime-syntax", "components/foo.component.html")
        self.assertTrue(selector.matches(view))

    def _make_html_view(self, file_name: str) -> sublime.View:
        return self._make_view("Packages/HTML/HTML.sublime-syntax", file_name)

    def test_pattern_asterisk(self) -> None:
        """`*` to match one or more characters in a path segment"""
        selector = DocumentSelector([{"language": "html", "pattern": "a*c.html"}])
        # self.assertFalse(selector.matches(self._make_html_view("ac.html")))
        self.assertTrue(selector.matches(self._make_html_view("abc.html")))
        self.assertTrue(selector.matches(self._make_html_view("axyc.html")))

    def test_pattern_optional(self) -> None:
        """`?` to match on one character in a path segment"""
        selector = DocumentSelector([{"language": "html", "pattern": "a?c.html"}])
        self.assertTrue(selector.matches(self._make_html_view("axc.html")))
        self.assertTrue(selector.matches(self._make_html_view("ayc.html")))
        self.assertFalse(selector.matches(self._make_html_view("ac.html")))
        self.assertFalse(selector.matches(self._make_html_view("axyc.html")))

    def test_pattern_globstar(self) -> None:
        """`**` to match any number of path segments, including none"""
        selector = DocumentSelector([{"language": "html", "pattern": "**/abc.html"}])
        self.assertTrue(selector.matches(self._make_html_view("foo/bar/abc.html")))
        self.assertFalse(selector.matches(self._make_html_view("asdf/qwerty/abc.htm")))

    def test_pattern_grouping(self) -> None:
        """`{}` to group conditions (e.g. `**/*.{ts,js}` matches all TypeScript and JavaScript files)"""
        selector = DocumentSelector([{"pattern": "**/*.{ts,js}"}])
        self.assertTrue(selector.matches(self._make_view(
            "Packages/JavaScript/TypeScript.sublime-syntax", "foo/bar.ts")))
        self.assertTrue(selector.matches(self._make_view(
            "Packages/JavaScript/JavaScript.sublime-syntax", "asdf/qwerty.js")))
        self.assertFalse(selector.matches(self._make_view(
            "Packages/JavaScript/TypeScript.sublime-syntax", "foo/bar.no-match-ts")))
        self.assertFalse(selector.matches(self._make_view(
            "Packages/JavaScript/JavaScript.sublime-syntax", "asdf/qwerty.no-match-js")))

    def test_pattern_character_range(self) -> None:
        """
        `[]` to declare a range of characters to match in a path segment (e.g., `example.[0-9]` to match on
        `example.0`, `example.1`, …)
        """
        selector = DocumentSelector([{"language": "html", "pattern": "example.[0-9]"}])
        self.assertTrue(selector.matches(self._make_html_view("example.0")))
        self.assertTrue(selector.matches(self._make_html_view("example.1")))
        self.assertTrue(selector.matches(self._make_html_view("example.2")))
        self.assertTrue(selector.matches(self._make_html_view("example.3")))
        self.assertTrue(selector.matches(self._make_html_view("example.4")))
        self.assertTrue(selector.matches(self._make_html_view("example.5")))
        self.assertTrue(selector.matches(self._make_html_view("example.6")))
        self.assertTrue(selector.matches(self._make_html_view("example.7")))
        self.assertTrue(selector.matches(self._make_html_view("example.8")))
        self.assertTrue(selector.matches(self._make_html_view("example.9")))
        self.assertFalse(selector.matches(self._make_html_view("example.10")))

    def test_pattern_negated_character_range(self) -> None:
        """
        `[!...]` to negate a range of characters to match in a path segment (e.g., `example.[!0-9]` to match on
        `example.a`, `example.b`, but not `example.0`)
        """
        selector = DocumentSelector([{"language": "html", "pattern": "example.[!0-9]"}])
        self.assertTrue(selector.matches(self._make_html_view("example.a")))
        self.assertTrue(selector.matches(self._make_html_view("example.b")))
        self.assertTrue(selector.matches(self._make_html_view("example.c")))
        self.assertFalse(selector.matches(self._make_html_view("example.0")))
        self.assertFalse(selector.matches(self._make_html_view("example.1")))
        self.assertFalse(selector.matches(self._make_html_view("example.2")))
        self.assertFalse(selector.matches(self._make_html_view("example.3")))
        self.assertFalse(selector.matches(self._make_html_view("example.4")))
        self.assertFalse(selector.matches(self._make_html_view("example.5")))
        self.assertFalse(selector.matches(self._make_html_view("example.6")))
        self.assertFalse(selector.matches(self._make_html_view("example.7")))
        self.assertFalse(selector.matches(self._make_html_view("example.8")))
        self.assertFalse(selector.matches(self._make_html_view("example.9")))
