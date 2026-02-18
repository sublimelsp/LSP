from __future__ import annotations

from LSP.plugin.core.types import basescope2languageid
from LSP.plugin.core.types import diff
from LSP.plugin.core.types import DocumentSelector_
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
        self._opened_views: list[sublime.View] = []

    def tearDown(self) -> None:
        for view in self._opened_views:
            view.close()
        self._opened_views.clear()

    def _make_view(self, syntax: str, file_name: str) -> sublime.View:
        view = sublime.active_window().new_file(sublime.NewFileFlags.NONE, syntax)
        self._opened_views.append(view)
        view.set_scratch(True)
        self.assertFalse(view.is_loading())
        view.file_name = MagicMock(return_value=file_name)
        return view

    def test_language(self) -> None:
        selector = DocumentSelector_([{"language": "plaintext"}])
        view = self._make_view("Packages/Text/Plain text.tmLanguage", "foobar.txt")
        self.assertTrue(selector.matches(view))
        view = self._make_view("Packages/Python/Python.sublime-syntax", "hello.py")
        self.assertFalse(selector.matches(view))

    def test_pattern_basics(self) -> None:
        selector = DocumentSelector_([{"language": "html", "pattern": "**/*.component.html"}])
        view = self._make_view("Packages/HTML/HTML.sublime-syntax", "index.html")
        self.assertFalse(selector.matches(view))
        view = self._make_view("Packages/HTML/HTML.sublime-syntax", "components/foo.component.html")
        self.assertTrue(selector.matches(view))

    def _make_html_view(self, file_name: str) -> sublime.View:
        return self._make_view("Packages/HTML/HTML.sublime-syntax", file_name)

    def test_pattern_asterisk(self) -> None:
        """`*` to match one or more characters in a path segment"""
        selector = DocumentSelector_([{"language": "html", "pattern": "a*c.html"}])
        # self.assertFalse(selector.matches(self._make_html_view("ac.html")))
        self.assertTrue(selector.matches(self._make_html_view("abc.html")))
        self.assertTrue(selector.matches(self._make_html_view("axyc.html")))

    def test_pattern_optional(self) -> None:
        """`?` to match on one character in a path segment"""
        selector = DocumentSelector_([{"language": "html", "pattern": "a?c.html"}])
        self.assertTrue(selector.matches(self._make_html_view("axc.html")))
        self.assertTrue(selector.matches(self._make_html_view("ayc.html")))
        self.assertFalse(selector.matches(self._make_html_view("ac.html")))
        self.assertFalse(selector.matches(self._make_html_view("axyc.html")))

    def test_pattern_globstar(self) -> None:
        """`**` to match any number of path segments, including none"""
        selector = DocumentSelector_([{"language": "html", "pattern": "**/abc.html"}])
        self.assertTrue(selector.matches(self._make_html_view("foo/bar/abc.html")))
        self.assertFalse(selector.matches(self._make_html_view("asdf/qwerty/abc.htm")))

    def test_pattern_grouping(self) -> None:
        """`{}` to group conditions (e.g. `**/*.{ts,js}` matches all TypeScript and JavaScript files)"""
        selector = DocumentSelector_([{"pattern": "**/*.{ts,js}"}])
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
        selector = DocumentSelector_([{"language": "html", "pattern": "example.[0-9]"}])
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
        selector = DocumentSelector_([{"language": "html", "pattern": "example.[!0-9]"}])
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

    def test_base_scope_to_language_id_mappings(self) -> None:
        scope_test_map = {
            "source.js.vite": "javascript",
            "source.c++": "cpp",
            "source.coffee.gulpfile": "coffeescript",
            "source.cs": "csharp",
            "source.css.tailwind": "css",
            "source.dosbatch": "bat",
            "source.fixedform-fortran": "fortran",
            "source.groovy.gradle": "groovy",
            "source.groovy.jenkins": "groovy",
            "source.js": "javascript",
            "source.js.eslint": "javascript",
            "source.js.gruntfile": "javascript",
            "source.js.gulpfile": "javascript",
            "source.js.postcss": "javascript",
            "source.js.puglint": "javascript",
            "source.js.react": "javascriptreact",
            "source.js.stylelint": "javascript",
            "source.js.unittest": "javascript",
            "source.js.webpack": "javascript",
            "source.json-tmlanguage": "jsonc",
            "source.json.babel": "json",
            "source.json.bower": "json",
            "source.json.composer": "json",
            "source.json.eslint": "json",
            "source.json.npm": "json",
            "source.json.postcss": "json",
            "source.json.puglint": "json",
            "source.json.settings": "json",
            "source.json.stylelint": "json",
            "source.json.sublime": "jsonc",
            "source.json.sublime.build": "jsonc",
            "source.json.sublime.color-scheme": "jsonc",
            "source.json.sublime.commands": "jsonc",
            "source.json.sublime.completions": "jsonc",
            "source.json.sublime.keymap": "jsonc",
            "source.json.sublime.macro": "jsonc",
            "source.json.sublime.menu": "jsonc",
            "source.json.sublime.mousemap": "jsonc",
            "source.json.sublime.project": "jsonc",
            "source.json.sublime.settings": "jsonc",
            "source.json.sublime.theme": "jsonc",
            "source.json.tern": "json",
            "source.jsx": "javascriptreact",
            "source.jsx.unittest": "javascriptreact",
            "source.Kotlin": "kotlin",
            "source.modern-fortran": "fortran",
            "source.objc": "objective-c",
            "source.objc++": "objective-cpp",
            "source.shader": "shaderlab",
            "source.shell.bash": "shellscript",
            "source.shell.docker": "shellscript",
            "source.shell.eslint": "shellscript",
            "source.shell.npm": "shellscript",
            "source.shell.ruby": "shellscript",
            "source.shell.stylelint": "shellscript",
            "source.ts": "typescript",
            "source.ts.react": "typescriptreact",
            "source.ts.unittest": "typescript",
            "source.tsx": "typescriptreact",
            "source.tsx.unittest": "typescriptreact",
            "source.unity.unity_shader": "shaderlab",
            "source.viml.vimrc": "viml",
            "source.yaml-tmlanguage": "yaml",
            "source.yaml.circleci": "yaml",
            "source.yaml.docker": "yaml",
            "source.yaml.eslint": "yaml",
            "source.yaml.lock": "yaml",
            "source.yaml.procfile": "yaml",
            "source.yaml.stylelint": "yaml",
            "source.yaml.sublime.syntax": "yaml",
            "source.yaml.yarn": "yaml",
            "text.advanced_csv": "csv",
            "text.django": "html",
            "text.html.basic": "html",
            "text.html.elixir": "html",
            "text.html.markdown.academicmarkdown": "markdown",
            "text.html.markdown.license": "markdown",
            "text.html.markdown.rmarkdown": "r",
            "text.html.ngx": "html",
            "text.jinja": "html",
            "text.plain": "plaintext",
            "text.plain.buildpacks": "plaintext",
            "text.plain.eslint": "plaintext",
            "text.plain.fastq": "plaintext",
            "text.plain.license": "plaintext",
            "text.plain.lnk": "plaintext",
            "text.plain.log": "plaintext",
            "text.plain.nodejs": "plaintext",
            "text.plain.pcb": "plaintext",
            "text.plain.ps": "plaintext",
            "text.plain.python": "plaintext",
            "text.plain.readme": "plaintext",
            "text.plain.ruby": "plaintext",
            "text.plain.sketch": "plaintext",
            "text.plain.visualstudio": "plaintext",
            "text.plist": "xml",
            "text.xml.plist": "xml",
            "text.xml.plist.textmate.preferences": "xml",
            "text.xml.sublime.snippet": "xml",
            "text.xml.svg": "xml",
            "text.xml.visualstudio": "xml",
        }

        for base_scope, expected_language_id in scope_test_map.items():
            self.assertEqual(basescope2languageid(base_scope), expected_language_id)
