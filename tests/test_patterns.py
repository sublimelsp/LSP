from __future__ import annotations

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
            'C:/project/foo/**')

    def test_project_relative_file_pattern_forward_slash_root(self) -> None:
        self.assertEqual(
            sublime_pattern_to_glob('//*.pyo', is_directory_pattern=False, root_path='C:/project'),
            'C:/project/**/*.pyo')

    def test_project_relative_nested_pattern_forward_slash_root(self) -> None:
        self.assertEqual(
            sublime_pattern_to_glob('//foo/bar', is_directory_pattern=True, root_path='C:/project'),
            'C:/project/foo/bar/**')

    def test_project_relative_directory_pattern_backslash_root(self) -> None:
        self.assertEqual(
            sublime_pattern_to_glob('//foo', is_directory_pattern=True, root_path=r'C:\project'),
            'C:/project/foo/**')

    def test_project_relative_file_pattern_backslash_root(self) -> None:
        self.assertEqual(
            sublime_pattern_to_glob('//*.pyo', is_directory_pattern=False, root_path=r'C:\project'),
            'C:/project/**/*.pyo')

    def test_project_relative_without_root_path(self) -> None:
        self.assertEqual(sublime_pattern_to_glob('//foo', is_directory_pattern=True), '//foo/**')
        self.assertEqual(sublime_pattern_to_glob('//*.pyo', is_directory_pattern=False), '//**/*.pyo')
