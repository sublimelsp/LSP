from __future__ import annotations
from ...protocol import *  # For backward compatibility with LSP packages.
from functools import total_ordering
from typing import Any, Callable, Generic, Iterable, Mapping, TypedDict, TypeVar, Union
from typing_extensions import NotRequired
import sublime

INT_MAX = 2**31 - 1
UINT_MAX = INT_MAX

R = TypeVar('R')


class Request(Generic[R]):

    __slots__ = ('method', 'params', 'view', 'progress', 'on_partial_result')

    def __init__(
        self,
        method: str,
        params: Any = None,
        view: sublime.View | None = None,
        progress: bool = False,
        on_partial_result: Callable[[Any], None] | None = None,
    ) -> None:
        self.method = method
        self.params = params
        self.view = view
        self.progress: bool | str = progress
        self.on_partial_result = on_partial_result

    @classmethod
    def initialize(cls, params: InitializeParams) -> Request:
        return Request("initialize", params)

    @classmethod
    def complete(cls, params: CompletionParams, view: sublime.View) -> Request:
        return Request("textDocument/completion", params, view)

    @classmethod
    def signatureHelp(cls, params: SignatureHelpParams, view: sublime.View) -> Request:
        return Request("textDocument/signatureHelp", params, view)

    @classmethod
    def codeAction(cls, params: CodeActionParams, view: sublime.View) -> Request:
        return Request("textDocument/codeAction", params, view)

    @classmethod
    def documentColor(cls, params: DocumentColorParams, view: sublime.View) -> Request:
        return Request('textDocument/documentColor', params, view)

    @classmethod
    def colorPresentation(cls, params: ColorPresentationParams, view: sublime.View) -> Request:
        return Request('textDocument/colorPresentation', params, view)

    @classmethod
    def willSaveWaitUntil(cls, params: WillSaveTextDocumentParams, view: sublime.View) -> Request:
        return Request("textDocument/willSaveWaitUntil", params, view)

    @classmethod
    def willRenameFiles(cls, params: RenameFilesParams) -> Request:
        return Request("workspace/willRenameFiles", params)

    @classmethod
    def documentSymbols(cls, params: DocumentSymbolParams, view: sublime.View) -> Request:
        return Request("textDocument/documentSymbol", params, view, progress=True)

    @classmethod
    def documentHighlight(cls, params: DocumentHighlightParams, view: sublime.View) -> Request:
        return Request("textDocument/documentHighlight", params, view)

    @classmethod
    def documentLink(cls, params: DocumentLinkParams, view: sublime.View) -> Request:
        return Request("textDocument/documentLink", params, view)

    @classmethod
    def semanticTokensFull(cls, params: SemanticTokensParams, view: sublime.View) -> Request:
        return Request("textDocument/semanticTokens/full", params, view)

    @classmethod
    def semanticTokensFullDelta(cls, params: SemanticTokensDeltaParams, view: sublime.View) -> Request:
        return Request("textDocument/semanticTokens/full/delta", params, view)

    @classmethod
    def semanticTokensRange(cls, params: SemanticTokensRangeParams, view: sublime.View) -> Request:
        return Request("textDocument/semanticTokens/range", params, view)

    @classmethod
    def prepareCallHierarchy(
        cls, params: CallHierarchyPrepareParams, view: sublime.View
    ) -> Request[list[CallHierarchyItem] | Error | None]:
        return Request("textDocument/prepareCallHierarchy", params, view, progress=True)

    @classmethod
    def incomingCalls(cls, params: CallHierarchyIncomingCallsParams) -> Request:
        return Request("callHierarchy/incomingCalls", params, None)

    @classmethod
    def outgoingCalls(cls, params: CallHierarchyOutgoingCallsParams) -> Request:
        return Request("callHierarchy/outgoingCalls", params, None)

    @classmethod
    def prepareTypeHierarchy(cls, params: TypeHierarchyPrepareParams, view: sublime.View) -> Request:
        return Request("textDocument/prepareTypeHierarchy", params, view, progress=True)

    @classmethod
    def supertypes(cls, params: TypeHierarchySupertypesParams) -> Request:
        return Request("typeHierarchy/supertypes", params, None)

    @classmethod
    def subtypes(cls, params: TypeHierarchySubtypesParams) -> Request:
        return Request("typeHierarchy/subtypes", params, None)

    @classmethod
    def resolveCompletionItem(cls, params: CompletionItem, view: sublime.View) -> Request:
        return Request("completionItem/resolve", params, view)

    @classmethod
    def resolveDocumentLink(cls, params: DocumentLink, view: sublime.View) -> Request:
        return Request("documentLink/resolve", params, view)

    @classmethod
    def inlayHint(cls, params: InlayHintParams, view: sublime.View) -> Request:
        return Request('textDocument/inlayHint', params, view)

    @classmethod
    def resolveInlayHint(cls, params: InlayHint, view: sublime.View) -> Request:
        return Request('inlayHint/resolve', params, view)

    @classmethod
    def rename(cls, params: RenameParams, view: sublime.View, progress: bool = False) -> Request:
        return Request('textDocument/rename', params, view, progress)

    @classmethod
    def prepareRename(cls, params: PrepareRenameParams, view: sublime.View, progress: bool = False) -> Request:
        return Request('textDocument/prepareRename', params, view, progress)

    @classmethod
    def selectionRange(cls, params: SelectionRangeParams) -> Request:
        return Request('textDocument/selectionRange', params)

    @classmethod
    def foldingRange(cls, params: FoldingRangeParams, view: sublime.View) -> Request:
        return Request('textDocument/foldingRange', params, view)

    @classmethod
    def workspaceSymbol(cls, params: WorkspaceSymbolParams) -> Request:
        return Request("workspace/symbol", params, None, progress=True)

    @classmethod
    def resolveWorkspaceSymbol(cls, params: WorkspaceSymbol) -> Request:
        return Request('workspaceSymbol/resolve', params)

    @classmethod
    def documentDiagnostic(cls, params: DocumentDiagnosticParams, view: sublime.View) -> Request:
        return Request('textDocument/diagnostic', params, view)

    @classmethod
    def workspaceDiagnostic(
        cls, params: WorkspaceDiagnosticParams, on_partial_result: Callable[[WorkspaceDiagnosticReport], None]
    ) -> Request:
        return Request('workspace/diagnostic', params, on_partial_result=on_partial_result)

    @classmethod
    def shutdown(cls) -> Request:
        return Request("shutdown")

    def __repr__(self) -> str:
        return self.method + " " + str(self.params)

    def to_payload(self, id: int) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": id,
            "method": self.method,
        }
        if self.params is not None:
            payload["params"] = self.params
        return payload


class Error(Exception):

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data

    @classmethod
    def from_lsp(cls, params: ResponseError) -> Error:
        return Error(params["code"], params["message"], params.get("data"))

    def to_lsp(self) -> dict[str, Any]:
        result = {"code": self.code, "message": super().__str__()}
        if self.data:
            result["data"] = self.data
        return result

    def __str__(self) -> str:
        return f"{super().__str__()} ({self.code})"

    @classmethod
    def from_exception(cls, ex: Exception) -> Error:
        return Error(ErrorCodes.InternalError, str(ex))


T = TypeVar('T', bound=Union[None, bool, int, Uint, float, str, Mapping[str, Any], Iterable[Any]])


class Response(Generic[T]):

    __slots__ = ('request_id', 'result')

    def __init__(self, request_id: Any, result: T) -> None:
        self.request_id = request_id
        self.result = result

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.request_id,
            "jsonrpc": "2.0",
            "result": self.result
        }


class Notification:

    __slots__ = ('method', 'params')

    def __init__(self, method: str, params: Any = None) -> None:
        self.method = method
        self.params = params

    @classmethod
    def initialized(cls) -> Notification:
        return Notification("initialized", {})

    @classmethod
    def didOpen(cls, params: DidOpenTextDocumentParams) -> Notification:
        return Notification("textDocument/didOpen", params)

    @classmethod
    def didChange(cls, params: DidChangeTextDocumentParams) -> Notification:
        return Notification("textDocument/didChange", params)

    @classmethod
    def willSave(cls, params: WillSaveTextDocumentParams) -> Notification:
        return Notification("textDocument/willSave", params)

    @classmethod
    def didSave(cls, params: DidSaveTextDocumentParams) -> Notification:
        return Notification("textDocument/didSave", params)

    @classmethod
    def didClose(cls, params: DidCloseTextDocumentParams) -> Notification:
        return Notification("textDocument/didClose", params)

    @classmethod
    def didRenameFiles(cls, params: RenameFilesParams) -> Notification:
        return Notification("workspace/didRenameFiles", params)

    @classmethod
    def didChangeConfiguration(cls, params: DidChangeConfigurationParams) -> Notification:
        return Notification("workspace/didChangeConfiguration", params)

    @classmethod
    def didChangeWatchedFiles(cls, params: DidChangeWatchedFilesParams) -> Notification:
        return Notification("workspace/didChangeWatchedFiles", params)

    @classmethod
    def didChangeWorkspaceFolders(cls, params: DidChangeWorkspaceFoldersParams) -> Notification:
        return Notification("workspace/didChangeWorkspaceFolders", params)

    @classmethod
    def exit(cls) -> Notification:
        return Notification("exit")

    def __repr__(self) -> str:
        return self.method + " " + str(self.params)

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "method": self.method,
        }
        if self.params is not None:
            payload["params"] = self.params
        return payload


@total_ordering
class Point:
    def __init__(self, row: int, col: int) -> None:
        self.row = int(row)
        self.col = int(col)  # in UTF-16

    def __repr__(self) -> str:
        return f"{self.row}:{self.col}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Point):
            return NotImplemented
        return self.row == other.row and self.col == other.col

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Point):
            return NotImplemented
        return (self.row, self.col) < (other.row, other.col)

    @classmethod
    def from_lsp(cls, point: Position) -> Point:
        return Point(point['line'], point['character'])

    def to_lsp(self) -> Position:
        return {
            "line": self.row,
            "character": self.col
        }


class ResponseError(TypedDict):
    code: int
    message: str
    data: NotRequired['LSPAny']


class ResolvedCodeLens(TypedDict):
    range: Range
    command: Command
    uses_cached_command: NotRequired[bool]


# Temporary for backward compatibility with LSP packages.
RangeLsp = Range
