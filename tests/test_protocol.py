from LSP.plugin.core.protocol import Point
import unittest

LSP_POSITION = {'line': 10, 'character': 4}


class PointTests(unittest.TestCase):

    def test_conversion(self):
        point = Point.from_lsp(LSP_POSITION)
        self.assertEqual(point.row, 10)
        self.assertEqual(point.col, 4)
