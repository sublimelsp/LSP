import sublime
try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass

from collections import OrderedDict


class DiagnosticSeverity(object):
    Error = 1
    Warning = 2
    Information = 3
    Hint = 4


class SymbolKind(object):
    File = 1
    Module = 2
    Namespace = 3
    Package = 4
    Class = 5
    Method = 6
    Property = 7
    Field = 8
    Constructor = 9
    Enum = 10
    Interface = 11
    Function = 12
    Variable = 13
    Constant = 14
    String = 15
    Number = 16
    Boolean = 17
    Array = 18


class CompletionItemKind(object):
    Text = 1
    Method = 2
    Function = 3
    Constructor = 4
    Field = 5
    Variable = 6
    Class = 7
    Interface = 8
    Module = 9
    Property = 10
    Unit = 11
    Value = 12
    Enum = 13
    Keyword = 14
    Snippet = 15
    Color = 16
    File = 17
    Reference = 18


class Request:
    def __init__(self, method, params):
        self.method = method
        self.params = params
        self.jsonrpc = "2.0"

    @classmethod
    def initialize(cls, params):
        return Request("initialize", params)

    @classmethod
    def hover(cls, params: dict):
        return Request("textDocument/hover", params)

    @classmethod
    def complete(cls, params: dict):
        return Request("textDocument/completion", params)

    @classmethod
    def signatureHelp(cls, params: dict):
        return Request("textDocument/signatureHelp", params)

    @classmethod
    def references(cls, params: dict):
        return Request("textDocument/references", params)

    @classmethod
    def definition(cls, params: dict):
        return Request("textDocument/definition", params)

    @classmethod
    def rename(cls, params: dict):
        return Request("textDocument/rename", params)

    @classmethod
    def codeAction(cls, params: dict):
        return Request("textDocument/codeAction", params)

    @classmethod
    def executeCommand(cls, params: dict):
        return Request("workspace/executeCommand", params)

    @classmethod
    def formatting(cls, params: dict):
        return Request("textDocument/formatting", params)

    @classmethod
    def rangeFormatting(cls, params: dict):
        return Request("textDocument/rangeFormatting", params)

    @classmethod
    def documentSymbols(cls, params: dict):
        return Request("textDocument/documentSymbol", params)

    @classmethod
    def resolveCompletionItem(cls, params: dict):
        return Request("completionItem/resolve", params)

    def __repr__(self):
        return self.method + " " + str(self.params)

    def to_payload(self, id):
        r = OrderedDict()  # type: OrderedDict[str, Any]
        r["jsonrpc"] = "2.0"
        r["id"] = id
        r["method"] = self.method
        if self.params is not None:
            r["params"] = self.params
        else:
            r["params"] = dict()
        return r


class Notification:
    def __init__(self, method, params):
        self.method = method
        self.params = params
        self.jsonrpc = "2.0"

    @classmethod
    def initialized(cls):
        return Notification("initialized", None)

    @classmethod
    def didOpen(cls, params: dict):
        return Notification("textDocument/didOpen", params)

    @classmethod
    def didChange(cls, params: dict):
        return Notification("textDocument/didChange", params)

    @classmethod
    def didSave(cls, params: dict):
        return Notification("textDocument/didSave", params)

    @classmethod
    def didClose(cls, params: dict):
        return Notification("textDocument/didClose", params)

    @classmethod
    def didChangeConfiguration(cls, params: dict):
        return Notification("workspace/didChangeConfiguration", params)

    @classmethod
    def exit(cls):
        return Notification("exit", None)

    def __repr__(self):
        return self.method + " " + str(self.params)

    def to_payload(self):
        r = OrderedDict()  # type: OrderedDict[str, Any]
        r["jsonrpc"] = "2.0"
        r["method"] = self.method
        if self.params is not None:
            r["params"] = self.params
        else:
            r["params"] = dict()
        return r


class Point(object):
    def __init__(self, row: int, col: int) -> None:
        self.row = int(row)
        self.col = int(col)

    def __repr__(self):
        return "{}:{}".format(self.row, self.col)

    @classmethod
    def from_lsp(cls, point: dict) -> 'Point':
        return Point(point['line'], point['character'])

    def to_lsp(self) -> dict:
        r = OrderedDict()  # type: OrderedDict[str, Any]
        r['line'] = self.row
        r['character'] = self.col
        return r

    @classmethod
    def from_text_point(self, view: sublime.View, point: int) -> 'Point':
        return Point(*view.rowcol(point))

    def to_text_point(self, view) -> int:
        return view.text_point(self.row, self.col)


class Range(object):
    def __init__(self, start: Point, end: Point) -> None:
        self.start = start
        self.end = end

    def __repr__(self):
        return "({} {})".format(self.start, self.end)

    @classmethod
    def from_lsp(cls, range: dict) -> 'Range':
        return Range(Point.from_lsp(range['start']), Point.from_lsp(range['end']))

    def to_lsp(self) -> dict:
        r = OrderedDict()  # type: OrderedDict[str, Any]
        r['start'] = self.start.to_lsp()
        r['end'] = self.end.to_lsp()
        return r

    @classmethod
    def from_region(self, view: sublime.View, region: sublime.Region) -> 'Range':
        return Range(
            Point.from_text_point(view, region.begin()),
            Point.from_text_point(view, region.end())
        )

    def to_region(self, view: sublime.View) -> sublime.Region:
        return sublime.Region(self.start.to_text_point(view), self.end.to_text_point(view))


class Diagnostic(object):
    def __init__(self, message, range, severity, source, lsp_diagnostic):
        self.message = message
        self.range = range
        self.severity = severity
        self.source = source
        self._lsp_diagnostic = lsp_diagnostic

    @classmethod
    def from_lsp(cls, lsp_diagnostic):
        return Diagnostic(
            # crucial keys
            lsp_diagnostic['message'],
            Range.from_lsp(lsp_diagnostic['range']),
            # optional keys
            lsp_diagnostic.get('severity', DiagnosticSeverity.Error),
            lsp_diagnostic.get('source'),
            lsp_diagnostic
        )

    def to_lsp(self):
        return self._lsp_diagnostic
