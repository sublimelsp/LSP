from .typing import Any, Dict, Iterable, List, Mapping, Optional, TypedDict, Union
from .url import filename_to_uri
from .url import uri_to_filename
import os
import sublime


TextDocumentSyncKindNone = 0
TextDocumentSyncKindFull = 1
TextDocumentSyncKindIncremental = 2


class DiagnosticSeverity:
    Error = 1
    Warning = 2
    Information = 3
    Hint = 4


class CompletionItemTag:
    Deprecated = 1


class InsertTextFormat:
    PlainText = 1
    Snippet = 2


class DocumentHighlightKind:
    Unknown = 0
    Text = 1
    Read = 2
    Write = 3


class SignatureHelpTriggerKind:
    Invoked = 1
    TriggerCharacter = 2
    ContentChange = 3


CodeDescription = TypedDict('CodeDescription', {
    'href': str
}, total=True)


ExecuteCommandParams = TypedDict('ExecuteCommandParams', {
    'command': str,
    'arguments': Optional[List[Any]],
}, total=False)


Command = TypedDict('Command', {
    'title': str,
    'command': str,
    'arguments': Optional[List[Any]],
})


CodeAction = TypedDict('CodeAction', {
    'title': str,
    'kind': Optional[str],
    'diagnostics': Optional[List[Any]],
    'isPreferred': Optional[bool],
    'edit': Optional[dict],
    'command': Optional[Command],
})


ParameterInformation = TypedDict('ParameterInformation', {
    'label': Union[str, List[int]],
    'documentation': Union[str, Dict[str, str]]
}, total=False)


SignatureInformation = TypedDict('SignatureInformation', {
    'label': str,
    'documentation': Union[str, Dict[str, str]],
    'parameters': List[ParameterInformation]
}, total=False)


SignatureHelp = TypedDict('SignatureHelp', {
    'signatures': List[SignatureInformation],
    'activeSignature': int,
    'activeParameter': int,
}, total=False)


SignatureHelpContext = TypedDict('SignatureHelpContext', {
    'triggerKind': int,
    'triggerCharacter': str,
    'isRetrigger': bool,
    'activeSignatureHelp': SignatureHelp
}, total=False)


class Request:

    __slots__ = ('method', 'params', 'view')

    def __init__(self, method: str, params: Optional[Mapping[str, Any]] = None,
                 view: Optional[sublime.View] = None) -> None:
        self.method = method
        self.params = params
        self.view = view

    @classmethod
    def initialize(cls, params: dict) -> 'Request':
        return Request("initialize", params)

    @classmethod
    def hover(cls, params: dict, view: sublime.View) -> 'Request':
        return Request("textDocument/hover", params, view)

    @classmethod
    def complete(cls, params: dict, view: sublime.View) -> 'Request':
        return Request("textDocument/completion", params, view)

    @classmethod
    def signatureHelp(cls, params: dict, view: sublime.View) -> 'Request':
        return Request("textDocument/signatureHelp", params, view)

    @classmethod
    def references(cls, params: dict, view: sublime.View) -> 'Request':
        return Request("textDocument/references", params, view)

    @classmethod
    def prepareRename(cls, params: dict, view: sublime.View) -> 'Request':
        return Request("textDocument/prepareRename", params, view)

    @classmethod
    def rename(cls, params: dict, view: sublime.View) -> 'Request':
        return Request("textDocument/rename", params, view)

    @classmethod
    def codeAction(cls, params: dict, view: sublime.View) -> 'Request':
        return Request("textDocument/codeAction", params, view)

    @classmethod
    def documentColor(cls, params: dict, view: sublime.View) -> 'Request':
        return Request('textDocument/documentColor', params, view)

    @classmethod
    def executeCommand(cls, params: Mapping[str, Any]) -> 'Request':
        return Request("workspace/executeCommand", params)

    @classmethod
    def workspaceSymbol(cls, params: dict) -> 'Request':
        return Request("workspace/symbol", params)

    @classmethod
    def formatting(cls, params: dict, view: sublime.View) -> 'Request':
        return Request("textDocument/formatting", params, view)

    @classmethod
    def willSaveWaitUntil(cls, params: dict, view: sublime.View) -> 'Request':
        return Request("textDocument/willSaveWaitUntil", params, view)

    @classmethod
    def rangeFormatting(cls, params: dict, view: sublime.View) -> 'Request':
        return Request("textDocument/rangeFormatting", params, view)

    @classmethod
    def documentSymbols(cls, params: dict, view: sublime.View) -> 'Request':
        return Request("textDocument/documentSymbol", params, view)

    @classmethod
    def documentHighlight(cls, params: dict, view: sublime.View) -> 'Request':
        return Request("textDocument/documentHighlight", params, view)

    @classmethod
    def resolveCompletionItem(cls, params: dict, view: sublime.View) -> 'Request':
        return Request("completionItem/resolve", params, view)

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


class Error(Exception):

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data

    @classmethod
    def from_lsp(cls, params: Any) -> "Error":
        return Error(params["code"], params["message"], params.get("data"))

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

    def extend(self, rge: 'Range') -> 'Range':
        """
        Extends current range to fully include another range. If another range is already fully
        enclosed within the current range then nothing changes.

        :param    rge: The region to extend current with

        :returns: The extended region (itself)
        """
        if rge.contains(self.start):
            self.start = rge.start
        if rge.contains(self.end):
            self.end = rge.end
        return self


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


class DiagnosticRelatedInformation:

    def __init__(self, location: Location, message: str) -> None:
        self.location = location
        self.message = message

    @classmethod
    def from_lsp(cls, lsp_related_information: dict) -> 'DiagnosticRelatedInformation':
        return DiagnosticRelatedInformation(
            Location.from_lsp(lsp_related_information["location"]),
            lsp_related_information["message"])


class Diagnostic:
    def __init__(
        self,
        message: str,
        range: Range,
        severity: int,
        code: Union[None, int, str],
        code_description: Optional[CodeDescription],
        source: Optional[str],
        lsp_diagnostic: dict,
        related_info: List[DiagnosticRelatedInformation]
    ) -> None:
        self.message = message
        self.range = range
        self.severity = severity
        self.code = code
        self.code_description = code_description
        self.source = source
        self._lsp_diagnostic = lsp_diagnostic
        self.related_info = related_info
        self.code

    @classmethod
    def from_lsp(cls, lsp_diagnostic: dict) -> 'Diagnostic':
        return Diagnostic(
            # crucial keys
            lsp_diagnostic['message'],
            Range.from_lsp(lsp_diagnostic['range']),
            # optional keys
            lsp_diagnostic.get('severity', DiagnosticSeverity.Error),
            lsp_diagnostic.get('code'),
            lsp_diagnostic.get('codeDescription'),
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

    def __hash__(self) -> int:
        return hash((self.name, self.path))

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

    def includes_uri(self, uri: str) -> bool:
        return uri.startswith(self.uri())
