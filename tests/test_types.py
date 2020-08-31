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

    def test_pattern(self) -> None:
        selector = DocumentSelector([{"language": "html", "pattern": "**/*.component.html"}])
        view = self._make_view("Packages/HTML/HTML.sublime-syntax", "index.html")
        self.assertFalse(selector.matches(view))
        view = self._make_view("Packages/HTML/HTML.sublime-syntax", "components/foo.component.html")
        self.assertTrue(selector.matches(view))
