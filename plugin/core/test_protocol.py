from .protocol import (
    Point, Range, Diagnostic, DiagnosticSeverity, Request, Notification
)
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
        self.assertEquals(lsp_point['line'], 10)
        self.assertEquals(lsp_point['character'], 4)


class RangeTests(unittest.TestCase):

    def test_lsp_conversion(self):
        range = Range.from_lsp(LSP_RANGE)
        self.assertEquals(range.start.row, 10)
        self.assertEquals(range.start.col, 4)
        self.assertEquals(range.end.row, 11)
        self.assertEquals(range.end.col, 3)
        lsp_range = range.to_lsp()
        self.assertEquals(lsp_range['start']['line'], 10)
        self.assertEquals(lsp_range['start']['character'], 4)
        self.assertEquals(lsp_range['end']['line'], 11)
        self.assertEquals(lsp_range['end']['character'], 3)


class DiagnosticTests(unittest.TestCase):

    def test_lsp_conversion(self):
        diag = Diagnostic.from_lsp(LSP_MINIMAL_DIAGNOSTIC)
        self.assertEquals(diag.message, 'message')
        self.assertEquals(diag.severity, DiagnosticSeverity.Error)
        self.assertEquals(diag.source, None)
        self.assertEquals(diag.to_lsp(), LSP_MINIMAL_DIAGNOSTIC)

    def test_full_lsp_conversion(self):
        diag = Diagnostic.from_lsp(LSP_FULL_DIAGNOSTIC)
        self.assertEquals(diag.message, 'message')
        self.assertEquals(diag.severity, DiagnosticSeverity.Warning)
        self.assertEquals(diag.source, 'pyls')
        self.assertEquals(diag.to_lsp(), LSP_FULL_DIAGNOSTIC)


class RequestTests(unittest.TestCase):

    def test_initialize(self):
        req = Request.initialize({"param": 1})
        payload = req.to_payload(1)
        self.assertEquals(payload["jsonrpc"], "2.0")
        self.assertEquals(payload["id"], 1)
        self.assertEquals(payload["method"], "initialize")
        self.assertEquals(payload["params"], {"param": 1})


class NotificationTests(unittest.TestCase):

    def test_initialized(self):
        notification = Notification.initialized()
        payload = notification.to_payload()
        self.assertEquals(payload["jsonrpc"], "2.0")
        self.assertNotIn("id", payload)
        self.assertEquals(payload["method"], "initialized")
        self.assertEquals(payload["params"], dict())
