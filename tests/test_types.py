import unittest
from LSP.plugin.core.types import diff


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
