from .typing import Any, Dict, Iterable, List, Mapping, Optional, TypedDict, Union
from .url import filename_to_uri
import os
import sublime

INT_MAX = 2**31 - 1
UINT_MAX = INT_MAX

TextDocumentSyncKindNone = 0
TextDocumentSyncKindFull = 1
TextDocumentSyncKindIncremental = 2


class DiagnosticSeverity:
    Error = 1
    Warning = 2
    Information = 3
    Hint = 4


class DiagnosticTag:
    Unnecessary = 1
    Deprecated = 2


class CodeActionTriggerKind:
    Invoked = 1
    Automatic = 2


class CompletionItemKind:
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


class CompletionItemTag:
    Deprecated = 1


class SymbolKind:
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


class SymbolTag:
    Deprecated = 1


class InsertTextFormat:
    PlainText = 1
    Snippet = 2


class DocumentHighlightKind:
    Text = 1
    Read = 2
    Write = 3


class SignatureHelpTriggerKind:
    Invoked = 1
    TriggerCharacter = 2
    ContentChange = 3


class InsertTextMode:
    AsIs = 1
    AdjustIndentation = 2


class SemanticTokenTypes:
    Namespace = "namespace"
    Type = "type"
    Class = "class"
    Enum = "enum"
    Interface = "interface"
    Struct = "struct"
    TypeParameter = "typeParameter"
    Parameter = "parameter"
    Variable = "variable"
    Property = "property"
    EnumMember = "enumMember"
    Event = "event"
    Function = "function"
    Method = "method"
    Macro = "macro"
    Keyword = "keyword"
    Modifier = "modifier"
    Comment = "comment"
    String = "string"
    Number = "number"
    Regexp = "regexp"
    Operator = "operator"
    Decorator = "decorator"


class SemanticTokenModifiers:
    Declaration = "declaration"
    Definition = "definition"
    Readonly = "readonly"
    Static = "static"
    Deprecated = "deprecated"
    Abstract = "abstract"
    Async = "async"
    Modification = "modification"
    Documentation = "documentation"
    DefaultLibrary = "defaultLibrary"


DocumentUri = str

Position = TypedDict('Position', {
    'line': int,
    'character': int
})

Range = TypedDict('Range', {
    'start': Position,
    'end': Position
})

TextDocumentIdentifier = TypedDict('TextDocumentIdentifier', {
    'uri': DocumentUri,
}, total=True)

TextDocumentPositionParams = TypedDict('TextDocumentPositionParams', {
    'textDocument': TextDocumentIdentifier,
    'position': Position,
}, total=True)

ExperimentalTextDocumentRangeParams = TypedDict('ExperimentalTextDocumentRangeParams', {
    'textDocument': TextDocumentIdentifier,
    'position': Position,
    'range': Range,
}, total=True)

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
}, total=True)


CodeActionDisabledInformation = TypedDict('CodeActionDisabledInformation', {
    'reason': str
}, total=True)


CodeLens = TypedDict('CodeLens', {
    'range': Range,
    'command': Optional[Command],
    'data': Any,
    # Custom property to bring along the name of the session
    'session_name': Optional[str]
}, total=True)


ParameterInformation = TypedDict('ParameterInformation', {
    'label': Union[str, List[int]],
    'documentation': Union[str, Dict[str, str]]
}, total=False)


SignatureInformation = TypedDict('SignatureInformation', {
    'label': str,
    'documentation': Union[str, Dict[str, str]],
    'parameters': List[ParameterInformation],
    'activeParameter': int
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


Location = TypedDict('Location', {
    'uri': DocumentUri,
    'range': Range
}, total=True)

DocumentSymbol = TypedDict('DocumentSymbol', {
    'name': str,
    'detail': Optional[str],
    'kind': int,
    'tags': Optional[List[int]],
    'deprecated': Optional[bool],
    'range': Range,
    'selectionRange': Range,
    'children': Optional[List[Any]]  # mypy doesn't support recurive types like Optional[List['DocumentSymbol']]
}, total=True)

SymbolInformation = TypedDict('SymbolInformation', {
    'name': str,
    'kind': int,
    'tags': Optional[List[int]],
    'deprecated': Optional[bool],
    'location': Location,
    'containerName': Optional[str]
}, total=True)

LocationLink = TypedDict('LocationLink', {
    'originSelectionRange': Optional[Range],
    'targetUri': DocumentUri,
    'targetRange': Range,
    'targetSelectionRange': Range
}, total=False)

DiagnosticRelatedInformation = TypedDict('DiagnosticRelatedInformation', {
    'location': Location,
    'message': str
}, total=False)

Diagnostic = TypedDict('Diagnostic', {
    'range': Range,
    'severity': int,
    'code': Union[int, str],
    'codeDescription': CodeDescription,
    'source': str,
    'message': str,
    'tags': List[int],
    'relatedInformation': List[DiagnosticRelatedInformation]
}, total=False)

CodeAction = TypedDict('CodeAction', {
    'title': str,
    'kind': str,  # NotRequired
    'diagnostics': List[Diagnostic],  # NotRequired
    'isPreferred': bool,  # NotRequired
    'disabled': CodeActionDisabledInformation,  # NotRequired
    'edit': dict,  # NotRequired
    'command': Command,  # NotRequired
    'data': Any  # NotRequired
}, total=False)

CodeActionContext = TypedDict('CodeActionContext', {
    'diagnostics': List[Diagnostic],
    'only': List[str],  # NotRequired
    'triggerKind': int,  # NotRequired
}, total=False)

CodeActionParams = TypedDict('CodeActionParams', {
    'textDocument': TextDocumentIdentifier,
    'range': Range,
    'context': CodeActionContext,
}, total=True)

TextEdit = TypedDict('TextEdit', {
    'newText': str,
    'range': Range
}, total=True)

CompletionItemLabelDetails = TypedDict('CompletionItemLabelDetails', {
    'detail': str,
    'description': str
}, total=False)

InsertReplaceEdit = TypedDict('InsertReplaceEdit', {
    'newText': str,
    'insert': Range,
    'replace': Range
}, total=True)

CompletionItem = TypedDict('CompletionItem', {
    'additionalTextEdits': List[TextEdit],
    'command': Command,
    'commitCharacters': List[str],
    'data': Any,
    'deprecated': bool,
    'detail': str,
    'documentation': Union[str, Dict[str, str]],
    'filterText': str,
    'insertText': str,
    'insertTextFormat': InsertTextFormat,
    'insertTextMode': InsertTextMode,
    'kind': int,
    'label': str,
    'labelDetails': CompletionItemLabelDetails,
    'preselect': bool,
    'sortText': str,
    'tags': List[int],
    'textEdit': Union[TextEdit, InsertReplaceEdit]
}, total=False)

CompletionList = TypedDict('CompletionList', {
    'isIncomplete': bool,
    'items': List[CompletionItem],
}, total=True)

DocumentLink = TypedDict('DocumentLink', {
    'range': Range,
    'target': DocumentUri,
    'tooltip': str,
    'data': Any
}, total=False)

MarkedString = Union[str, Dict[str, str]]

MarkupContent = Dict[str, str]

Hover = TypedDict('Hover', {
    'contents': Union[MarkedString, MarkupContent, List[MarkedString]],
    'range': Range,
}, total=False)

PublishDiagnosticsParams = TypedDict('PublishDiagnosticsParams', {
    'uri': DocumentUri,
    'version': Optional[int],
    'diagnostics': List[Diagnostic],
}, total=False)


FileSystemWatcher = TypedDict('FileSystemWatcher', {
    'globPattern': str,
    'kind': int,
}, total=True)

DidChangeWatchedFilesRegistrationOptions = TypedDict('DidChangeWatchedFilesRegistrationOptions', {
    'watchers': List[FileSystemWatcher],
}, total=True)

InlayHintParams = TypedDict('InlayHintParams', {
    'textDocument': TextDocumentIdentifier,
    'range': Range,
}, total=True)

InlayHintLabelPart = TypedDict('InlayHintLabelPart', {
    'value': str,
    'tooltip': Union[str, MarkupContent],  # NotRequired
    'location': Location,  # NotRequired
    'command':  Command  # NotRequired
}, total=False)


class InlayHintKind:
    Type = 1
    Parameter = 2


InlayHint = TypedDict('InlayHint', {
    'position': Position,
    'label': Union[str, List[InlayHintLabelPart]],
    'kind': int,  # NotRequired
    'textEdits': List[TextEdit],  # NotRequired
    'tooltip': Union[str, MarkupContent],  # NotRequired
    'paddingLeft': bool,  # NotRequired
    'paddingRight': bool,  # NotRequired
    'data': Any  # NotRequired
}, total=False)

InlayHintResponse = Union[List[InlayHint], None]

WatchKind = int
WatchKindCreate = 1
WatchKindChange = 2
WatchKindDelete = 4

FileChangeType = int
FileChangeTypeCreated = 1
FileChangeTypeChanged = 2
FileChangeTypeDeleted = 3

FileEvent = TypedDict("FileEvent", {
    "uri": DocumentUri,
    "type": FileChangeType,
}, total=True)


class Request:

    __slots__ = ('method', 'params', 'view', 'progress')

    def __init__(
        self,
        method: str,
        params: Any = None,
        view: Optional[sublime.View] = None,
        progress: bool = False
    ) -> None:
        self.method = method
        self.params = params
        self.view = view
        self.progress = progress  # type: Union[bool, str]

    @classmethod
    def initialize(cls, params: Mapping[str, Any]) -> 'Request':
        return Request("initialize", params)

    @classmethod
    def complete(cls, params: Mapping[str, Any], view: sublime.View) -> 'Request':
        return Request("textDocument/completion", params, view)

    @classmethod
    def signatureHelp(cls, params: Mapping[str, Any], view: sublime.View) -> 'Request':
        return Request("textDocument/signatureHelp", params, view)

    @classmethod
    def codeAction(cls, params: Mapping[str, Any], view: sublime.View) -> 'Request':
        return Request("textDocument/codeAction", params, view)

    @classmethod
    def documentColor(cls, params: Mapping[str, Any], view: sublime.View) -> 'Request':
        return Request('textDocument/documentColor', params, view)

    @classmethod
    def willSaveWaitUntil(cls, params: Mapping[str, Any], view: sublime.View) -> 'Request':
        return Request("textDocument/willSaveWaitUntil", params, view)

    @classmethod
    def documentSymbols(cls, params: Mapping[str, Any], view: sublime.View) -> 'Request':
        return Request("textDocument/documentSymbol", params, view)

    @classmethod
    def documentHighlight(cls, params: Mapping[str, Any], view: sublime.View) -> 'Request':
        return Request("textDocument/documentHighlight", params, view)

    @classmethod
    def documentLink(cls, params: Mapping[str, Any], view: sublime.View) -> 'Request':
        return Request("textDocument/documentLink", params, view)

    @classmethod
    def semanticTokensFull(cls, params: Mapping[str, Any], view: sublime.View) -> 'Request':
        return Request("textDocument/semanticTokens/full", params, view)

    @classmethod
    def semanticTokensFullDelta(cls, params: Mapping[str, Any], view: sublime.View) -> 'Request':
        return Request("textDocument/semanticTokens/full/delta", params, view)

    @classmethod
    def semanticTokensRange(cls, params: Mapping[str, Any], view: sublime.View) -> 'Request':
        return Request("textDocument/semanticTokens/range", params, view)

    @classmethod
    def resolveCompletionItem(cls, params: CompletionItem, view: sublime.View) -> 'Request':
        return Request("completionItem/resolve", params, view)

    @classmethod
    def resolveDocumentLink(cls, params: DocumentLink, view: sublime.View) -> 'Request':
        return Request("documentLink/resolve", params, view)

    @classmethod
    def inlayHint(cls, params: InlayHintParams, view: sublime.View) -> 'Request':
        return Request('textDocument/inlayHint', params, view)

    @classmethod
    def resolveInlayHint(cls, params: InlayHint, view: sublime.View) -> 'Request':
        return Request('inlayHint/resolve', params, view)

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

    def __init__(self, method: str, params: Any = None) -> None:
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
    def didChangeWatchedFiles(cls, params: dict) -> 'Notification':
        return Notification("workspace/didChangeWatchedFiles", params)

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
    def from_lsp(cls, point: Position) -> 'Point':
        return Point(point['line'], point['character'])

    def to_lsp(self) -> Position:
        return {
            "line": self.row,
            "character": self.col
        }


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


# Temporary for backward compatibility with LSP packages.

RangeLsp = Range
