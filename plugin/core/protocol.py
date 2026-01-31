from __future__ import annotations
from ...protocol import *  # For backward compatibility with LSP packages.
from functools import total_ordering
from typing import Any, Callable, Generic, Iterable, Mapping, TypedDict, TypeVar, Union
from typing_extensions import NotRequired, TypeAlias
import sublime

INT_MAX = 2**31 - 1
UINT_MAX = INT_MAX

LspPayload: TypeAlias = Union[None, bool, int, Uint, float, str, Mapping[str, Any], Iterable[Any]]
P = TypeVar('P', bound=LspPayload)
R = TypeVar('R', bound=LspPayload)


class JsonRpcPayload(TypedDict):
    jsonrpc: str
    error: NotRequired[ResponseError]
    id: NotRequired[str | int]
    method: NotRequired[str]
    params: NotRequired[Any]
    result: NotRequired[Any]


class Request(Generic[P, R]):

    __slots__ = ('method', 'params', 'view', 'progress', 'on_partial_result')

    def __init__(
        self,
        method: str,
        params: P = None,
        view: sublime.View | None = None,
        progress: bool = False,
        on_partial_result: Callable[[R], None] | None = None,
    ) -> None:
        self.method = method
        self.params = params
        self.view = view
        self.progress: bool | str = progress
        self.on_partial_result = on_partial_result

    @classmethod
    def initialize(cls, params: InitializeParams) -> Request[InitializeParams, InitializeResult]:
        return Request("initialize", params)

    @classmethod
    def complete(
        cls, params: CompletionParams, view: sublime.View
    ) -> Request[CompletionParams, list[CompletionItem] | CompletionList | None]:
        return Request("textDocument/completion", params, view)

    @classmethod
    def signatureHelp(
        cls, params: SignatureHelpParams, view: sublime.View
    ) -> Request[SignatureHelpParams, SignatureHelp | None]:
        return Request("textDocument/signatureHelp", params, view)

    @classmethod
    def codeAction(
        cls, params: CodeActionParams, view: sublime.View
    ) -> Request[CodeActionParams, list[Command | CodeAction] | None]:
        return Request("textDocument/codeAction", params, view)

    @classmethod
    def documentColor(
        cls, params: DocumentColorParams, view: sublime.View
    ) -> Request[DocumentColorParams, list[ColorInformation]]:
        return Request('textDocument/documentColor', params, view)

    @classmethod
    def colorPresentation(
        cls, params: ColorPresentationParams, view: sublime.View
    ) -> Request[ColorPresentationParams, list[ColorPresentation]]:
        return Request('textDocument/colorPresentation', params, view)

    @classmethod
    def willSaveWaitUntil(
        cls, params: WillSaveTextDocumentParams, view: sublime.View
    ) -> Request[WillSaveTextDocumentParams, list[TextEdit] | None]:
        return Request("textDocument/willSaveWaitUntil", params, view)

    @classmethod
    def willRenameFiles(cls, params: RenameFilesParams) -> Request[RenameFilesParams, WorkspaceEdit | None]:
        return Request("workspace/willRenameFiles", params)

    @classmethod
    def documentSymbols(
        cls, params: DocumentSymbolParams, view: sublime.View
    ) -> Request[DocumentSymbolParams, list[DocumentSymbol] | list[SymbolInformation] | None]:
        return Request("textDocument/documentSymbol", params, view, progress=True)

    @classmethod
    def documentHighlight(
        cls, params: DocumentHighlightParams, view: sublime.View
    ) -> Request[DocumentHighlightParams, list[DocumentHighlight] | None]:
        return Request("textDocument/documentHighlight", params, view)

    @classmethod
    def documentLink(
        cls, params: DocumentLinkParams, view: sublime.View
    ) -> Request[DocumentLinkParams, list[DocumentLink]]:
        return Request("textDocument/documentLink", params, view)

    @classmethod
    def semanticTokensFull(
        cls, params: SemanticTokensParams, view: sublime.View
    ) -> Request[SemanticTokensParams, SemanticTokens | None]:
        return Request("textDocument/semanticTokens/full", params, view)

    @classmethod
    def semanticTokensFullDelta(
        cls, params: SemanticTokensDeltaParams, view: sublime.View
    ) -> Request[SemanticTokensDeltaParams, SemanticTokens | SemanticTokensDelta | None]:
        return Request("textDocument/semanticTokens/full/delta", params, view)

    @classmethod
    def semanticTokensRange(
        cls, params: SemanticTokensRangeParams, view: sublime.View
    ) -> Request[SemanticTokensRangeParams, SemanticTokens | None]:
        return Request("textDocument/semanticTokens/range", params, view)

    @classmethod
    def prepareCallHierarchy(
        cls, params: CallHierarchyPrepareParams, view: sublime.View
    ) -> Request[CallHierarchyPrepareParams, list[CallHierarchyItem] | None]:
        return Request("textDocument/prepareCallHierarchy", params, view, progress=True)

    @classmethod
    def incomingCalls(
        cls, params: CallHierarchyIncomingCallsParams
    ) -> Request[CallHierarchyIncomingCallsParams, list[CallHierarchyIncomingCall] | None]:
        return Request("callHierarchy/incomingCalls", params, None)

    @classmethod
    def outgoingCalls(
        cls, params: CallHierarchyOutgoingCallsParams
    ) -> Request[CallHierarchyOutgoingCallsParams, list[CallHierarchyOutgoingCall] | None]:
        return Request("callHierarchy/outgoingCalls", params, None)

    @classmethod
    def prepareTypeHierarchy(
        cls, params: TypeHierarchyPrepareParams, view: sublime.View
    ) -> Request[TypeHierarchyPrepareParams, list[TypeHierarchyItem] | None]:
        return Request("textDocument/prepareTypeHierarchy", params, view, progress=True)

    @classmethod
    def supertypes(
        cls, params: TypeHierarchySupertypesParams
    ) -> Request[TypeHierarchySupertypesParams, list[TypeHierarchyItem] | None]:
        return Request("typeHierarchy/supertypes", params, None)

    @classmethod
    def subtypes(
        cls, params: TypeHierarchySubtypesParams
    ) -> Request[TypeHierarchySubtypesParams, list[TypeHierarchyItem] | None]:
        return Request("typeHierarchy/subtypes", params, None)

    @classmethod
    def resolveCompletionItem(
        cls, params: CompletionItem, view: sublime.View
    ) -> Request[CompletionItem, CompletionItem]:
        return Request("completionItem/resolve", params, view)

    @classmethod
    def resolveDocumentLink(cls, params: DocumentLink, view: sublime.View) -> Request[DocumentLink, DocumentLink]:
        return Request("documentLink/resolve", params, view)

    @classmethod
    def inlayHint(cls, params: InlayHintParams, view: sublime.View) -> Request[InlayHintParams, list[InlayHint] | None]:
        return Request('textDocument/inlayHint', params, view)

    @classmethod
    def resolveInlayHint(cls, params: InlayHint, view: sublime.View) -> Request[InlayHint, InlayHint]:
        return Request('inlayHint/resolve', params, view)

    @classmethod
    def rename(
        cls, params: RenameParams, view: sublime.View, progress: bool = False
    ) -> Request[RenameParams, WorkspaceEdit | None]:
        return Request('textDocument/rename', params, view, progress)

    @classmethod
    def prepareRename(
        cls, params: PrepareRenameParams, view: sublime.View, progress: bool = False
    ) -> Request[PrepareRenameParams, PrepareRenameResult | None]:
        return Request('textDocument/prepareRename', params, view, progress)

    @classmethod
    def selectionRange(cls, params: SelectionRangeParams) -> Request[SelectionRangeParams, list[SelectionRange] | None]:
        return Request('textDocument/selectionRange', params)

    @classmethod
    def foldingRange(
        cls, params: FoldingRangeParams, view: sublime.View
    ) -> Request[FoldingRangeParams, list[FoldingRange] | None]:
        return Request('textDocument/foldingRange', params, view)

    @classmethod
    def formatting(
        cls, params: DocumentFormattingParams, view: sublime.View
    ) -> Request[DocumentFormattingParams, list[TextEdit] | None]:
        return Request('textDocument/formatting', params, view, progress=True)

    @classmethod
    def range_formatting(
        cls, params: DocumentRangeFormattingParams, view: sublime.View
    ) -> Request[DocumentRangeFormattingParams, list[TextEdit] | None]:
        return Request('textDocument/rangeFormatting', params, view, progress=True)

    @classmethod
    def ranges_formatting(
        cls, params: DocumentRangesFormattingParams, view: sublime.View
    ) -> Request[DocumentRangesFormattingParams, list[TextEdit] | None]:
        return Request('textDocument/rangesFormatting', params, view, progress=True)

    @classmethod
    def workspaceSymbol(
        cls, params: WorkspaceSymbolParams
    ) -> Request[WorkspaceSymbolParams, list[SymbolInformation] | list[WorkspaceSymbol] | None]:
        return Request("workspace/symbol", params, None, progress=True)

    @classmethod
    def resolveWorkspaceSymbol(cls, params: WorkspaceSymbol) -> Request[WorkspaceSymbol, WorkspaceSymbol]:
        return Request('workspaceSymbol/resolve', params)

    @classmethod
    def documentDiagnostic(
        cls, params: DocumentDiagnosticParams, view: sublime.View
    ) -> Request[DocumentDiagnosticParams, DocumentDiagnosticReport]:
        return Request('textDocument/diagnostic', params, view)

    @classmethod
    def workspaceDiagnostic(
        cls, params: WorkspaceDiagnosticParams, on_partial_result: Callable[[WorkspaceDiagnosticReport], None]
    ) -> Request[WorkspaceDiagnosticParams, WorkspaceDiagnosticReport]:
        return Request('workspace/diagnostic', params, on_partial_result=on_partial_result)

    @classmethod
    def shutdown(cls) -> Request[None, None]:
        return Request("shutdown")

    def __repr__(self) -> str:
        return self.method + " " + str(self.params)

    def to_payload(self, request_id: int) -> JsonRpcPayload:
        payload: JsonRpcPayload = {
            "jsonrpc": "2.0",
            "id": request_id,
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

    def to_lsp(self) -> ResponseError:
        result: ResponseError = {"code": self.code, "message": super().__str__()}
        if self.data:
            result["data"] = self.data
        return result

    def __str__(self) -> str:
        return f"{super().__str__()} ({self.code})"

    @classmethod
    def from_exception(cls, ex: Exception) -> Error:
        return Error(ErrorCodes.InternalError, str(ex))


class Response(Generic[P]):

    __slots__ = ('request_id', 'result')

    def __init__(self, request_id: str | int, result: P) -> None:
        self.request_id = request_id
        self.result = result

    def to_payload(self) -> JsonRpcPayload:
        return {
            "id": self.request_id,
            "jsonrpc": "2.0",
            "result": self.result
        }


class Notification(Generic[P]):

    __slots__ = ('method', 'params')

    def __init__(self, method: str, params: P = None) -> None:
        self.method = method
        self.params = params

    @classmethod
    def initialized(cls) -> Notification[InitializedParams]:
        return Notification("initialized", {})

    @classmethod
    def didOpen(cls, params: DidOpenTextDocumentParams) -> Notification[DidOpenTextDocumentParams]:
        return Notification("textDocument/didOpen", params)

    @classmethod
    def didChange(cls, params: DidChangeTextDocumentParams) -> Notification[DidChangeTextDocumentParams]:
        return Notification("textDocument/didChange", params)

    @classmethod
    def willSave(cls, params: WillSaveTextDocumentParams) -> Notification[WillSaveTextDocumentParams]:
        return Notification("textDocument/willSave", params)

    @classmethod
    def didSave(cls, params: DidSaveTextDocumentParams) -> Notification[DidSaveTextDocumentParams]:
        return Notification("textDocument/didSave", params)

    @classmethod
    def didClose(cls, params: DidCloseTextDocumentParams) -> Notification[DidCloseTextDocumentParams]:
        return Notification("textDocument/didClose", params)

    @classmethod
    def didRenameFiles(cls, params: RenameFilesParams) -> Notification[RenameFilesParams]:
        return Notification("workspace/didRenameFiles", params)

    @classmethod
    def didChangeConfiguration(cls, params: DidChangeConfigurationParams) -> Notification[DidChangeConfigurationParams]:
        return Notification("workspace/didChangeConfiguration", params)

    @classmethod
    def didChangeWatchedFiles(cls, params: DidChangeWatchedFilesParams) -> Notification[DidChangeWatchedFilesParams]:
        return Notification("workspace/didChangeWatchedFiles", params)

    @classmethod
    def didChangeWorkspaceFolders(
        cls, params: DidChangeWorkspaceFoldersParams
    ) -> Notification[DidChangeWorkspaceFoldersParams]:
        return Notification("workspace/didChangeWorkspaceFolders", params)

    @classmethod
    def exit(cls) -> Notification[None]:
        return Notification("exit")

    def __repr__(self) -> str:
        return self.method + " " + str(self.params)

    def to_payload(self) -> JsonRpcPayload:
        payload: JsonRpcPayload = {
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
    data: NotRequired[LSPAny]


class ResolvedCodeLens(TypedDict):
    range: Range
    command: Command
    uses_cached_command: NotRequired[bool]


# Temporary for backward compatibility with LSP packages.
RangeLsp = Range
