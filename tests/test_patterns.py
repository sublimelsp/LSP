from __future__ import annotations

from LSP.plugin.core.types import matches_pattern
from LSP.plugin.core.types import sublime_pattern_to_glob
import sys
import unittest


class PatternToGlobTests(unittest.TestCase):

    def test_basic_directory_patterns(self) -> None:
        self.assertEqual(sublime_pattern_to_glob('.git', is_directory_pattern=True), '**/.git/**')
        self.assertEqual(sublime_pattern_to_glob('CVS', is_directory_pattern=True), '**/CVS/**')
        self.assertEqual(sublime_pattern_to_glob('.Trash-*', is_directory_pattern=True), '**/.Trash-*/**')

    def test_complex_directory_patterns(self) -> None:
        self.assertEqual(sublime_pattern_to_glob('*/foo', is_directory_pattern=True), '**/foo/**')
        self.assertEqual(sublime_pattern_to_glob('foo/bar', is_directory_pattern=True), '**/foo/bar/**')
        self.assertEqual(sublime_pattern_to_glob('foo/bar/', is_directory_pattern=True), '**/foo/bar/**')
        self.assertEqual(sublime_pattern_to_glob('/foo', is_directory_pattern=True), '/foo/**')

    def test_basic_file_patterns(self) -> None:
        self.assertEqual(sublime_pattern_to_glob('*.pyc', is_directory_pattern=False), '**/*.pyc')
        self.assertEqual(sublime_pattern_to_glob('.DS_Store', is_directory_pattern=False), '**/.DS_Store')

    def test_complex_file_patterns(self) -> None:
        self.assertEqual(sublime_pattern_to_glob('*/foo.py', is_directory_pattern=False), '**/foo.py')
        self.assertEqual(sublime_pattern_to_glob('/*.pyo', is_directory_pattern=False), '/**/*.pyo')

    def test_slash_star_or_star_slash_matches_any_directory(self) -> None:
        self.assertEqual(sublime_pattern_to_glob('foo/*', is_directory_pattern=True), '**/foo/**')
        self.assertEqual(sublime_pattern_to_glob('foo/*/', is_directory_pattern=True), '**/foo/**')
        self.assertEqual(sublime_pattern_to_glob('foo/*.py', is_directory_pattern=False), '**/foo/**/*.py')

    def test_question_mark_not_matches_slash_in_basic_pattern(self) -> None:
        self.assertEqual(sublime_pattern_to_glob('foo?bar', is_directory_pattern=True), '**/foo?bar/**')

    def test_question_mark_matches_slash_in_complex_pattern(self) -> None:
        self.assertEqual(sublime_pattern_to_glob('/foo?bar', is_directory_pattern=True), '/foo{?,/}bar/**')

    def test_project_relative_patterns(self) -> None:
        self.assertEqual(
            sublime_pattern_to_glob('//foo', is_directory_pattern=True, root_path='/Users/me'), '/Users/me/foo/**')
        self.assertEqual(
            sublime_pattern_to_glob('//*.pyo', is_directory_pattern=False, root_path='/Users/me'), '/Users/me/**/*.pyo')
        # Without root_path those will be treated as absolute paths even when starting with multiple slashes.
        self.assertEqual(sublime_pattern_to_glob('//foo', is_directory_pattern=True), '//foo/**')
        self.assertEqual(sublime_pattern_to_glob('//*.pyo', is_directory_pattern=False), '//**/*.pyo')


@unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
class PatternToGlobWindowsTests(unittest.TestCase):

    def test_project_relative_directory_pattern_forward_slash_root(self) -> None:
        self.assertEqual(
            sublime_pattern_to_glob('//foo', is_directory_pattern=True, root_path='C:/project'),
            '**/C:/project/foo/**')

    def test_project_relative_file_pattern_forward_slash_root(self) -> None:
        self.assertEqual(
            sublime_pattern_to_glob('//*.pyo', is_directory_pattern=False, root_path='C:/project'),
            '**/C:/project/**/*.pyo')

    def test_project_relative_nested_pattern_forward_slash_root(self) -> None:
        self.assertEqual(
            sublime_pattern_to_glob('//foo/bar', is_directory_pattern=True, root_path='C:/project'),
            '**/C:/project/foo/bar/**')

    def test_project_relative_directory_pattern_backslash_root(self) -> None:
        self.assertEqual(
            sublime_pattern_to_glob('//foo', is_directory_pattern=True, root_path=r'C:\Users\me\project'),
            'C:/Users/me/project/foo/**')

    def test_project_relative_file_pattern_backslash_root(self) -> None:
        self.assertEqual(
            sublime_pattern_to_glob('//*.pyo', is_directory_pattern=False, root_path=r'C:\Users\me\project'),
            'C:/Users/me/project/**/*.pyo')

    def test_project_relative_without_root_path(self) -> None:
        self.assertEqual(sublime_pattern_to_glob('//foo', is_directory_pattern=True), '//foo/**')
        self.assertEqual(sublime_pattern_to_glob('//*.pyo', is_directory_pattern=False), '//**/*.pyo')


@unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
class MatchesPatternWindowsTests(unittest.TestCase):

    def test_absolute_path(self) -> None:
        self.assertTrue(matches_pattern(r"C:\foo\bar.py", ["*.py"]))

    def test_no_match(self) -> None:
        self.assertFalse(matches_pattern(r"C:\foo\bar.py", ["*.js"]))

    def test_case_insensitive(self) -> None:
        self.assertTrue(matches_pattern(r"C:\foo\bar.PY", ["*.py"]))

    def test_directory_wildcard(self) -> None:
        self.assertTrue(matches_pattern(r"C:\foo\bar.py", [r"C:\*\bar.py"]))

    def test_exact_path(self) -> None:
        self.assertTrue(matches_pattern(r"C:\foo\bar.py", [r"C:\foo\bar.py"]))

    def test_unc_path(self) -> None:
        self.assertTrue(matches_pattern(r"\\server\share\file.py", ["*.py"]))


class MatchesPatternTests(unittest.TestCase):

    def test_returns_false_for_non_list(self) -> None:
        self.assertFalse(matches_pattern("/foo/bar.py", None))
        self.assertFalse(matches_pattern("/foo/bar.py", "*.py"))
        self.assertFalse(matches_pattern("/foo/bar.py", {"*.py"}))

    def test_returns_false_for_empty_list(self) -> None:
        self.assertFalse(matches_pattern("/foo/bar.py", []))

    def test_skips_non_string_patterns(self) -> None:
        self.assertFalse(matches_pattern("/foo/bar.py", [None, 42, True]))

    def test_matches_exact_path(self) -> None:
        self.assertTrue(matches_pattern("/foo/bar.py", ["/foo/bar.py"]))

    def test_matches_wildcard_extension(self) -> None:
        self.assertTrue(matches_pattern("/foo/bar.py", ["*.py"]))
        self.assertTrue(matches_pattern("/foo/bar.py", ["/*.py"]))

    def test_no_match(self) -> None:
        self.assertFalse(matches_pattern("/foo/bar.py", ["*.js"]))

    def test_star_matches_zero_characters(self) -> None:
        self.assertTrue(matches_pattern("/foo/bar.py", ["/foo/bar*.py"]))

    def test_star_matches_multiple_characters(self) -> None:
        self.assertTrue(matches_pattern("/foo/bar.py", ["/foo/b*r.py"]))

    def test_no_slash_matches_file_or_dir(self) -> None:
        self.assertTrue(matches_pattern("/foo/bar.py", ["*.py"]))
        self.assertTrue(matches_pattern("/foo/bar/baz.py", ["bar"]))
        self.assertFalse(matches_pattern("/foo/bar/baz.py", ["baz"]))

    def test_leading_slash_anchors_to_path_start(self) -> None:
        self.assertTrue(matches_pattern("/foo/bar.py", ["/foo/bar.py"]))
        self.assertFalse(matches_pattern("/baz/foo/bar.py", ["/foo/bar.py"]))

    def test_leading_slash_anchors_wildcard_pattern(self) -> None:
        self.assertTrue(matches_pattern("/foo/bar.py", ["/foo/*.py"]))
        self.assertFalse(matches_pattern("/baz/foo/bar.py", ["/foo/*.py"]))

    def test_no_leading_slash_star_matches_any_prefix(self) -> None:
        self.assertTrue(matches_pattern("/foo/bar.py", ["*.py"]))
        self.assertTrue(matches_pattern("/baz/foo/bar.py", ["*.py"]))

    def test_trailing_slash_matches_contained_dirs_and_files(self) -> None:
        self.assertTrue(matches_pattern("/foo/bar.py", ["/foo/"]))
        self.assertTrue(matches_pattern("/baz/foo/bar.py", ["*/foo/"]))

    def test_matches_first_matching_pattern(self) -> None:
        self.assertTrue(matches_pattern("/foo/bar.py", ["*.js", "*.py"]))

    def test_matches_path_wildcard(self) -> None:
        self.assertTrue(matches_pattern("/foo/bar.py", ["/foo/*.py"]))
        self.assertTrue(matches_pattern("/foo/bar/baz.py", ["/foo/*.py"]))

    def test_no_match_different_directory(self) -> None:
        self.assertFalse(matches_pattern("/baz/bar.py", ["/foo/*.py"]))

    def test_question_mark_matches_single_character(self) -> None:
        self.assertTrue(matches_pattern("/foo/bar.py", ["/foo/ba?.py"]))

    def test_question_mark_no_match_on_zero_characters(self) -> None:
        self.assertFalse(matches_pattern("/foo/ba.py", ["/foo/ba?.py"]))

    def test_question_mark_no_match_on_two_characters(self) -> None:
        self.assertFalse(matches_pattern("/foo/barr.py", ["/foo/ba?.py"]))

    def test_question_mark_matches_slash(self) -> None:
        self.assertTrue(matches_pattern("/foo/bar.py", ["/foo?bar.py"]))

    def test_mixed_valid_and_invalid_patterns(self) -> None:
        self.assertTrue(matches_pattern("/foo/bar.py", [42, "*.py"]))
