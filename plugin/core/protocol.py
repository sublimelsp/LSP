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


class InsertTextFormat:
    PlainText = 1
    Snippet = 2


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


class ErrorCode:
    # Defined by JSON RPC
    ParseError = -32700
    InvalidRequest = -32600
    MethodNotFound = -32601
    InvalidParams = -32602
    InternalError = -32603
    ServerErrorStart = -32099
    ServerErrorEnd = -32000
    ServerNotInitialized = -32002
    UnknownErrorCode = -32001

    # Defined by the protocol
    RequestCancelled = -32800
    ContentModified = -32801

    # Defined by us
    Timeout = -40000


class Error(Exception):

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data

    def to_lsp(self) -> Dict[str, Any]:
        result = {"code": self.code, "message": super().__str__()}
        if self.data:
            result["data"] = self.data
        return result

    def __str__(self) -> str:
        return "{} ({})".format(super().__str__(), self.code)

    @classmethod
    def from_exception(cls, ex: Exception) -> 'Error':
        return Error(ErrorCode.InternalError, str(ex))


class Response:

    __slots__ = ('request_id', 'result')

    def __init__(self, request_id: Any, result: Union[None, Mapping[str, Any], Iterable[Any]]) -> None:
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
    def willSave(cls, params: dict) -> 'Notification':
        return Notification("textDocument/willSave", params)

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
        self.col = int(col)  # in UTF-16

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
        return self.start.row <= point.row <= self.end.row and \
            (self.end.row > point.row or self.start.col <= point.col <= self.end.col)

    def intersects(self, rge: 'Range') -> bool:
        return self.contains(rge.start) or self.contains(rge.end) or \
            rge.contains(self.start) or rge.contains(self.end)


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
            [DiagnosticRelatedInformation.from_lsp(info) for info in lsp_diagnostic.get('relatedInformation') or []]
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

    @classmethod
    def from_path(cls, path: str) -> 'WorkspaceFolder':
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
