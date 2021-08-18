from LSP.plugin.core.protocol import Point, Range, Request, Notification
from LSP.plugin.core.transports import _encode, _decode
import unittest


LSP_START_POSITION = {'line': 10, 'character': 4}
LSP_END_POSITION = {'line': 11, 'character': 3}
LSP_RANGE = {'start': LSP_START_POSITION, 'end': LSP_END_POSITION}
LSP_MINIMAL_DIAGNOSTIC = {
    'message': 'message',
    'range': LSP_RANGE
}

LSP_FULL_DIAGNOSTIC = {
    'message': 'message',
    'range': LSP_RANGE,
    'severity': 2,  # warning
    'source': 'pyls'
}


class PointTests(unittest.TestCase):

    def test_lsp_conversion(self):
        point = Point.from_lsp(LSP_START_POSITION)
        self.assertEqual(point.row, 10)
        self.assertEqual(point.col, 4)
        lsp_point = point.to_lsp()
        self.assertEqual(lsp_point['line'], 10)
        self.assertEqual(lsp_point['character'], 4)


class RangeTests(unittest.TestCase):

    def test_lsp_conversion(self):
        range = Range.from_lsp(LSP_RANGE)
        self.assertEqual(range.start.row, 10)
        self.assertEqual(range.start.col, 4)
        self.assertEqual(range.end.row, 11)
        self.assertEqual(range.end.col, 3)
        lsp_range = range.to_lsp()
        self.assertEqual(lsp_range['start']['line'], 10)
        self.assertEqual(lsp_range['start']['character'], 4)
        self.assertEqual(lsp_range['end']['line'], 11)
        self.assertEqual(lsp_range['end']['character'], 3)

    def test_contains(self):
        range = Range.from_lsp(LSP_RANGE)
        point = Point.from_lsp(LSP_START_POSITION)
        self.assertTrue(range.contains(point))
        # Point inside of range with character offset lower than range end
        range = Range.from_lsp(LSP_RANGE)
        point = Point.from_lsp({'line': 10, 'character': 1})
        self.assertTrue(range.contains(point))
        # Point out of range with character offset lower than range end
        range = Range.from_lsp({
            'start': {'line': 0, 'character': 0},
            'end': {'line': 1, 'character': 4}
        })
        point = Point.from_lsp({'line': 12, 'character': 0})
        self.assertFalse(range.contains(point))
        # Point within first line of range.
        range = Range.from_lsp({
            'start': {'line': 0, 'character': 0},
            'end': {'line': 1, 'character': 4}
        })
        point = Point.from_lsp({'line': 0, 'character': 4})
        self.assertTrue(range.contains(point))

    def test_intersects(self):
        # range2 fully contained within range1
        range1 = Range.from_lsp({
            'start': {'line': 0, 'character': 0},
            'end': {'line': 1, 'character': 4}
        })
        range2 = Range.from_lsp({
            'start': {'line': 0, 'character': 2},
            'end': {'line': 0, 'character': 3}
        })
        self.assertTrue(range1.intersects(range2))
        # range2 intersecting end of range 1
        range1 = Range.from_lsp({
            'start': {'line': 0, 'character': 0},
            'end': {'line': 0, 'character': 3}
        })
        range2 = Range.from_lsp({
            'start': {'line': 0, 'character': 2},
            'end': {'line': 0, 'character': 4}
        })
        self.assertTrue(range1.intersects(range2))
        # range2 fully outside of range 1
        range1 = Range.from_lsp({
            'start': {'line': 0, 'character': 0},
            'end': {'line': 0, 'character': 3}
        })
        range2 = Range.from_lsp({
            'start': {'line': 2, 'character': 0},
            'end': {'line': 3, 'character': 0}
        })
        self.assertFalse(range1.intersects(range2))
        # range2 fully within range 1
        range1 = Range.from_lsp({
            'start': {'line': 0, 'character': 10},
            'end': {'line': 1, 'character': 20}
        })
        range2 = Range.from_lsp({
            'start': {'line': 0, 'character': 21},
            'end': {'line': 0, 'character': 22}
        })
        self.assertTrue(range1.intersects(range2))

    def test_extend(self) -> None:
        # includes range 1
        base_range = Range(Point(0, 0), Point(0, 0))
        other_range = Range(Point(0, 0), Point(0, 3))
        base_range.extend(other_range)
        self.assertEqual(base_range, other_range)
        # includes range 2
        base_range = Range(Point(1, 0), Point(1, 1))
        other_range = Range(Point(0, 0), Point(2, 0))
        base_range.extend(other_range)
        self.assertEqual(base_range, other_range)
        # is not extended
        base_range = Range(Point(1, 0), Point(1, 5))
        other_range = Range(Point(1, 1), Point(1, 2))
        base_range.extend(other_range)
        self.assertEqual(base_range, Range(Point(1, 0), Point(1, 5)))


class EncodingTests(unittest.TestCase):
    def test_encode(self):
        encoded = _encode({"text": "😃"})
        self.assertEqual(encoded, b'{"text":"\xF0\x9F\x98\x83"}')
        decoded = _decode(encoded)
        self.assertEqual(decoded, {"text": "😃"})


class RequestTests(unittest.TestCase):

    def test_initialize(self):
        req = Request.initialize({"param": 1})
        payload = req.to_payload(1)
        self.assertEqual(payload["jsonrpc"], "2.0")
        self.assertEqual(payload["id"], 1)
        self.assertEqual(payload["method"], "initialize")
        self.assertEqual(payload["params"], {"param": 1})

    def test_shutdown(self):
        req = Request.shutdown()
        payload = req.to_payload(1)
        self.assertEqual(payload["jsonrpc"], "2.0")
        self.assertEqual(payload["id"], 1)
        self.assertEqual(payload["method"], "shutdown")
        self.assertEqual(payload["params"], None)


class NotificationTests(unittest.TestCase):

    def test_initialized(self):
        notification = Notification.initialized()
        payload = notification.to_payload()
        self.assertEqual(payload["jsonrpc"], "2.0")
        self.assertNotIn("id", payload)
        self.assertEqual(payload["method"], "initialized")
        self.assertEqual(payload["params"], dict())

    def test_exit(self):
        notification = Notification.exit()
        payload = notification.to_payload()
        self.assertEqual(payload["jsonrpc"], "2.0")
        self.assertNotIn("id", payload)
        self.assertEqual(payload["method"], "exit")
        self.assertEqual(payload["params"], None)
