from .url import uri_to_filename
try:
    from typing import Any, List, Dict, Tuple, Callable, Optional
    assert Any and List and Dict and Tuple and Callable and Optional
except ImportError:
    pass


TextDocumentSyncKindNone = 0
TextDocumentSyncKindFull = 1
TextDocumentSyncKindIncremental = 2


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
    Object = 19
    Key = 20
    Null = 21
    EnumMember = 22
    Struct = 23
    Event = 24
    Operator = 25
    TypeParameter = 26


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
    Folder = 19
    EnumMember = 20
    Constant = 21
    Struct = 22
    Event = 23
    Operator = 24
    TypeParameter = 25


class DocumentHighlightKind(object):
    Unknown = 0
    Text = 1
    Read = 2
    Write = 3


class Request:
    def __init__(self, method: str, params: 'Optional[dict]') -> None:
        self.method = method
        self.params = params
        self.jsonrpc = "2.0"

    @classmethod
    def initialize(cls, params: dict) -> 'Request':
        return Request("initialize", params)

    @classmethod
    def hover(cls, params: dict) -> 'Request':
        return Request("textDocument/hover", params)

    @classmethod
    def complete(cls, params: dict) -> 'Request':
        return Request("textDocument/completion", params)

    @classmethod
    def signatureHelp(cls, params: dict) -> 'Request':
        return Request("textDocument/signatureHelp", params)

    @classmethod
    def references(cls, params: dict) -> 'Request':
        return Request("textDocument/references", params)

    @classmethod
    def definition(cls, params: dict) -> 'Request':
        return Request("textDocument/definition", params)

    @classmethod
    def rename(cls, params: dict) -> 'Request':
        return Request("textDocument/rename", params)

    @classmethod
    def codeAction(cls, params: dict) -> 'Request':
        return Request("textDocument/codeAction", params)

    @classmethod
    def executeCommand(cls, params: dict) -> 'Request':
        return Request("workspace/executeCommand", params)

    @classmethod
    def workspaceSymbol(cls, params: dict) -> 'Request':
        return Request("workspace/symbol", params)

    @classmethod
    def formatting(cls, params: dict) -> 'Request':
        return Request("textDocument/formatting", params)

    @classmethod
    def rangeFormatting(cls, params: dict) -> 'Request':
        return Request("textDocument/rangeFormatting", params)

    @classmethod
    def documentSymbols(cls, params: dict) -> 'Request':
        return Request("textDocument/documentSymbol", params)

    @classmethod
    def documentHighlight(cls, params: dict) -> 'Request':
        return Request("textDocument/documentHighlight", params)

    @classmethod
    def resolveCompletionItem(cls, params: dict) -> 'Request':
        return Request("completionItem/resolve", params)

    @classmethod
    def shutdown(cls) -> 'Request':
        return Request("shutdown", None)

    def __repr__(self) -> str:
        return self.method + " " + str(self.params)

    def to_payload(self, id) -> 'Dict[str, Any]':
        r = {
            "jsonrpc": "2.0",
            "id": id,
            "method": self.method
        }  # type: Dict[str, Any]
        if self.params is not None:
            r["params"] = self.params
        return r


class Response:
    def __init__(self, request_id: int, result: 'Optional[Dict[str, Any]]') -> None:
        self.request_id = request_id
        self.result = result
        self.jsonrpc = "2.0"

    def to_payload(self) -> 'Dict[str, Any]':
        r = {
            "id": self.request_id,
            "jsonrpc": self.jsonrpc,
            "result": self.result
        }
        return r


class Notification:
    def __init__(self, method: str, params: dict = {}) -> None:
        self.method = method
        self.params = params
        self.jsonrpc = "2.0"

    @classmethod
    def initialized(cls) -> 'Notification':
        return Notification("initialized")

    @classmethod
    def didOpen(cls, params: dict) -> 'Notification':
        return Notification("textDocument/didOpen", params)

    @classmethod
    def didChange(cls, params: dict) -> 'Notification':
        return Notification("textDocument/didChange", params)

    @classmethod
    def didSave(cls, params: dict) -> 'Notification':
        return Notification("textDocument/didSave", params)

    @classmethod
    def didClose(cls, params: dict) -> 'Notification':
        return Notification("textDocument/didClose", params)

    @classmethod
    def didChangeConfiguration(cls, params: dict) -> 'Notification':
        return Notification("workspace/didChangeConfiguration", params)

    @classmethod
    def exit(cls) -> 'Notification':
        return Notification("exit")

    def __repr__(self) -> str:
        return self.method + " " + str(self.params)

    def to_payload(self) -> 'Dict[str, Any]':
        r = {
            "jsonrpc": "2.0",
            "method": self.method
        }  # type: Dict[str, Any]
        if self.params is not None:
            r["params"] = self.params
        else:
            r["params"] = dict()
        return r


class Point(object):
    def __init__(self, row: int, col: int) -> None:
        self.row = int(row)
        self.col = int(col)

    def __repr__(self) -> str:
        return "{}:{}".format(self.row, self.col)

    @classmethod
    def from_lsp(cls, point: dict) -> 'Point':
        return Point(point['line'], point['character'])

    def to_lsp(self) -> 'Dict[str, Any]':
        return {
            "line": self.row,
            "character": self.col
        }


class Range(object):
    def __init__(self, start: Point, end: Point) -> None:
        self.start = start
        self.end = end

    def __repr__(self) -> str:
        return "({} {})".format(self.start, self.end)

    @classmethod
    def from_lsp(cls, range: dict) -> 'Range':
        return Range(Point.from_lsp(range['start']), Point.from_lsp(range['end']))

    def to_lsp(self) -> 'Dict[str, Any]':
        return {
            'start': self.start.to_lsp(),
            'end': self.end.to_lsp()
        }


def parse_workspace_edit(workspace_edit: Dict[str, Any]) -> 'Dict[str, List[Edit]]':
    changes = {}  # type: Dict[str, List[Edit]]
    if 'changes' in workspace_edit:
        for uri, file_changes in workspace_edit.get('changes', {}).items():
            changes[uri_to_filename(uri)] = list(Edit.from_lsp(change) for change in file_changes)
    if 'documentChanges' in workspace_edit:
        for document_change in workspace_edit.get('documentChanges', []):
            uri = document_change.get('textDocument').get('uri')
            changes[uri_to_filename(uri)] = list(Edit.from_lsp(change) for change in document_change.get('edits'))
    return changes


class Edit(object):

    def __init__(self, range: Range, newText: str) -> None:
        self.newText = newText
        self.range = range

    @classmethod
    def from_lsp(cls, edit: dict) -> 'Edit':
        return Edit(Range.from_lsp(edit.get('range', {})), edit.get('newText', ''))


class Diagnostic(object):
    def __init__(self, message: str, range: Range, severity: int,
                 source: 'Optional[str]', lsp_diagnostic: dict) -> None:
        self.message = message
        self.range = range
        self.severity = severity
        self.source = source
        self._lsp_diagnostic = lsp_diagnostic

    @classmethod
    def from_lsp(cls, lsp_diagnostic: dict) -> 'Diagnostic':
        return Diagnostic(
            # crucial keys
            lsp_diagnostic['message'],
            Range.from_lsp(lsp_diagnostic['range']),
            # optional keys
            lsp_diagnostic.get('severity', DiagnosticSeverity.Error),
            lsp_diagnostic.get('source'),
            lsp_diagnostic
        )

    def to_lsp(self) -> 'Dict[str, Any]':
        return self._lsp_diagnostic
