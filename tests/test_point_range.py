"""
Tests for Point.

To run this unit test install UnitTesting package and choose
"UnitTesting: Test current project" command.
"""

from unittest import TestCase

from LSP.main import Point
from LSP.main import Range


class test_point(TestCase):

    def test_valid_point(self):
        lsp_point = {'line': 10, 'character': 4}
        point = Point.from_lsp(lsp_point)
        self.assertEqual(point.row, 10)
        self.assertEqual(point.col, 4)

    def test_none_point(self):
        # expect TypeError if range object is None
        with self.assertRaises(TypeError):
            Point.from_lsp(None)

    def test_invalid_point(self):
        # expect KeyError if point is missing a key
        lsp_point = {'line': 10}
        with self.assertRaises(KeyError):
            Point.from_lsp(lsp_point)
        lsp_point = {'character': 10}
        with self.assertRaises(KeyError):
            Point.from_lsp(lsp_point)

        # expect ValueError if any value is not integer
        lsp_point = {'line': '10', 'character': '4'}
        with self.assertRaises(ValueError):
            Point.from_lsp(lsp_point)


class test_range(TestCase):

    def test_valid_range(self):
        lsp_range = {
            'start': {'line': 10, 'character': 4},
            'end': {'line': 20, 'character': 5}
        }
        range = Range.from_lsp(lsp_range)
        self.assertEqual(range.start.row, 10)
        self.assertEqual(range.start.col, 4)
        self.assertEqual(range.end.row, 20)
        self.assertEqual(range.end.col, 5)

    def test_none_range(self):
        # expect TypeError if range object is None
        with self.assertRaises(TypeError):
            Range.from_lsp(None)

    def test_invalid_range(self):
        # expect KeyError if 'end' key is missing
        lsp_range = {
            'start': {'line': 10, 'character': 4}
        }
        with self.assertRaises(KeyError):
            Range.from_lsp(lsp_range)

        # expect KeyError if 'start' key is missing
        lsp_range = {
            'end': {'line': 10, 'character': 4}
        }
        with self.assertRaises(KeyError):
            Range.from_lsp(lsp_range)

        # expect KeyError if point is missing a key
        lsp_range = {
            'start': {'line': 10, 'character': 4},
            'end': {'line': 20}
        }
        with self.assertRaises(KeyError):
            Range.from_lsp(lsp_range)

        # expect ValueError if any coordinate is not integer
        lsp_range = {
            'start': {'line': '10', 'character': '4'},
            'end': {'line': '20', 'character': '5'}
        }
        with self.assertRaises(ValueError):
            Range.from_lsp(lsp_range)
