from .typing import Any, List, Dict, Optional, Union, Mapping, Iterable
from .url import filename_to_uri
from .url import uri_to_filename
import os


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


symbol_kinds = list(range(SymbolKind.File, SymbolKind.TypeParameter + 1))


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


completion_item_kinds = list(range(CompletionItemKind.Text, CompletionItemKind.TypeParameter + 1))


class DocumentHighlightKind(object):
    Unknown = 0
    Text = 1
    Read = 2
    Write = 3


class Request:

    __slots__ = ('method', 'params')

    def __init__(self, method: str, params: Optional[Mapping[str, Any]] = None) -> None:
        self.method = method
        self.params = params

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
    def typeDefinition(cls, params: dict) -> 'Request':
        return Request("textDocument/typeDefinition", params)

    @classmethod
    def declaration(cls, params: dict) -> 'Request':
        return Request("textDocument/declaration", params)

    @classmethod
    def implementation(cls, params: dict) -> 'Request':
        return Request("textDocument/implementation", params)

    @classmethod
    def rename(cls, params: dict) -> 'Request':
        return Request("textDocument/rename", params)

    @classmethod
    def codeAction(cls, params: dict) -> 'Request':
        return Request("textDocument/codeAction", params)

    @classmethod
    def documentColor(cls, params: dict) -> 'Request':
        return Request('textDocument/documentColor', params)

    @classmethod
    def executeCommand(cls, params: Mapping[str, Any]) -> 'Request':
        return Request("workspace/executeCommand", params)

    @classmethod
    def workspaceSymbol(cls, params: dict) -> 'Request':
        return Request("workspace/symbol", params)

    @classmethod
    def formatting(cls, params: dict) -> 'Request':
        return Request("textDocument/formatting", params)

    @classmethod
    def willSaveWaitUntil(cls, params: dict) -> 'Request':
        return Request("textDocument/willSaveWaitUntil", params)

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
        return Request("shutdown")

    def __repr__(self) -> str:
        return self.method + " " + str(self.params)

    def to_payload(self, id: int) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": id,
            "method": self.method,
            "params": self.params
        }


class Response:

    __slots__ = ('request_id', 'result')

    def __init__(self, request_id: int, result: Union[None, Mapping[str, Any], Iterable[Any]]) -> None:
        self.request_id = request_id
        self.result = result

    def to_payload(self) -> Dict[str, Any]:
        r = {
            "id": self.request_id,
            "jsonrpc": "2.0",
            "result": self.result
        }
        return r


class Notification:

    __slots__ = ('method', 'params')

    def __init__(self, method: str, params: Optional[Mapping[str, Any]] = None) -> None:
        self.method = method
        self.params = params

    @classmethod
    def initialized(cls) -> 'Notification':
        return Notification("initialized", {})

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
    def didChangeWorkspaceFolders(cls, params: dict) -> 'Notification':
        return Notification("workspace/didChangeWorkspaceFolders", params)

    @classmethod
    def exit(cls) -> 'Notification':
        return Notification("exit")

    def __repr__(self) -> str:
        return self.method + " " + str(self.params)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "method": self.method,
            "params": self.params
        }


class Point(object):
    def __init__(self, row: int, col: int) -> None:
        self.row = int(row)
        self.col = int(col)

    def __repr__(self) -> str:
        return "{}:{}".format(self.row, self.col)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Point):
            raise NotImplementedError()
        return self.row == other.row and self.col == other.col

    @classmethod
    def from_lsp(cls, point: dict) -> 'Point':
        return Point(point['line'], point['character'])

    def to_lsp(self) -> Dict[str, Any]:
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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Range):
            raise NotImplementedError()

        return self.start == other.start and self.end == other.end

    @classmethod
    def from_lsp(cls, range: dict) -> 'Range':
        return Range(Point.from_lsp(range['start']), Point.from_lsp(range['end']))

    def to_lsp(self) -> Dict[str, Any]:
        return {
            'start': self.start.to_lsp(),
            'end': self.end.to_lsp()
        }

    def contains(self, point: Point) -> bool:
        return self.start.row <= point.row <= self.end.row and self.start.col <= point.col <= self.end.col

    def intersects(self, rge: 'Range') -> bool:
        return rge.start.row <= self.end.row and rge.start.col <= self.end.col and \
            rge.end.row >= self.start.row and rge.end.col >= self.start.col


class ContentChange(object):
    def __init__(self, text: str, range: Optional[Range] = None, range_length: Optional[int] = None) -> None:
        """

        [description]

        Arguments:
            text {str} -- The new text of the range/document
            range: 'Optional[Range]' {[type]} -- The range of the document that changed.
            range_length: 'Optional[int]' {[type]} -- The length of the range that got replaced.
        """
        self.text = text
        self.range = range
        self.range_length = range_length

    def to_lsp(self) -> Dict[str, Any]:
        change = {
            'text': self.text,
        }  # type: Dict[str, Any]
        if self.range:
            change['range'] = self.range.to_lsp(),
        if self.range_length:
            change['rangeLength'] = self.range_length
        return change

    def __eq__(self, other: Any) -> bool:
        return self.text == other.text and self.range == other.range and self.range_length == other.range_length

    def __repr__(self) -> str:
        return "{} {} '{}'".format(self.range, self.range_length, self.text)


class Location(object):
    def __init__(self, file_path: str, range: Range) -> None:
        self.file_path = file_path
        self.range = range

    @classmethod
    def from_lsp(cls, lsp_location: dict) -> 'Location':
        return Location(
            uri_to_filename(lsp_location["uri"]),
            Range.from_lsp(lsp_location["range"])
        )


class DiagnosticRelatedInformation(object):

    def __init__(self, location: Location, message: str) -> None:
        self.location = location
        self.message = message

    @classmethod
    def from_lsp(cls, lsp_related_information: dict) -> 'DiagnosticRelatedInformation':
        return DiagnosticRelatedInformation(
            Location.from_lsp(lsp_related_information["location"]),
            lsp_related_information["message"])


class Diagnostic(object):
    def __init__(self, message: str, range: Range, severity: int, source: Optional[str], lsp_diagnostic: dict,
                 related_info: List[DiagnosticRelatedInformation]) -> None:
        self.message = message
        self.range = range
        self.severity = severity
        self.source = source
        self._lsp_diagnostic = lsp_diagnostic
        self.related_info = related_info

    @classmethod
    def from_lsp(cls, lsp_diagnostic: dict) -> 'Diagnostic':
        return Diagnostic(
            # crucial keys
            lsp_diagnostic['message'],
            Range.from_lsp(lsp_diagnostic['range']),
            # optional keys
            lsp_diagnostic.get('severity', DiagnosticSeverity.Error),
            lsp_diagnostic.get('source'),
            lsp_diagnostic,
            [DiagnosticRelatedInformation.from_lsp(info) for info in lsp_diagnostic.get('relatedInformation', [])]
        )

    def to_lsp(self) -> Dict[str, Any]:
        return self._lsp_diagnostic

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Diagnostic):
            raise NotImplementedError()

        return self.message == other.message and self.range == other.range

    def __repr__(self) -> str:
        return str(self.range) + ":" + self.message


class WorkspaceFolder:

    __slots__ = ('name', 'path')

    def __init__(self, name: str, path: str) -> None:
        self.name = name
        self.path = path
        assert self.name
        assert self.path

    @classmethod
    def from_path(cls, path: str) -> 'WorkspaceFolder':
        assert os.path.isdir(path)
        assert os.path.isabs(path)
        return cls(os.path.basename(path) or path, path)

    def __repr__(self) -> str:
        return "{}('{}', '{}')".format(self.__class__.__name__, self.name, self.path)

    def __str__(self) -> str:
        return self.path

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, WorkspaceFolder):
            return self.name == other.name and self.path == other.path
        return False

    def to_lsp(self) -> Dict[str, str]:
        return {"name": self.name, "uri": self.uri()}

    def uri(self) -> str:
        return filename_to_uri(self.path)
