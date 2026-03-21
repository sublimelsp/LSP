# ruff: noqa: F405
from __future__ import annotations

from ...protocol import *  # For backward compatibility with LSP packages.  # noqa: F403
from functools import total_ordering
from typing import Any
from typing import Callable
from typing import Generic
from typing import List
from typing import Literal
from typing import TypedDict
from typing import TypeVar
from typing import Union
from typing_extensions import NotRequired
from typing_extensions import TypeAlias
import sublime

INT_MAX = 2**31 - 1
UINT_MAX = INT_MAX

P = TypeVar('P', bound=LSPAny)
R = TypeVar('R', bound=LSPAny)


class RequestMessage(TypedDict):
    jsonrpc: str
    id: str | int
    method: str
    params: NotRequired[Any]


class ResponseMessage(TypedDict):
    jsonrpc: str
    id: str | int
    result: NotRequired[Any]
    error: NotRequired[ResponseError]


class NotificationMessage(TypedDict):
    jsonrpc: str
    method: str
    params: NotRequired[Any]


JSONRPCMessage = Union[RequestMessage, ResponseMessage, NotificationMessage]


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
    def executeCommand(
        cls, params: ExecuteCommandParams, *, progress: bool = False
    ) -> Request[ExecuteCommandParams, R]:
        return Request("workspace/executeCommand", params, progress=progress)

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
    def onTypeFormatting(
        cls, params: DocumentOnTypeFormattingParams, view: sublime.View
    ) -> Request[DocumentOnTypeFormattingParams, list[TextEdit] | None]:
        return Request('textDocument/onTypeFormatting', params, view)

    @classmethod
    def rename(
        cls, params: RenameParams, view: sublime.View, *, progress: bool = False
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

    def to_payload(self, request_id: int) -> RequestMessage:
        payload: RequestMessage = {
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

    def to_payload(self) -> ResponseMessage:
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

    def to_payload(self) -> NotificationMessage:
        payload: NotificationMessage = {
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


class ApplyWorkspaceEditRequest(TypedDict):
    method: Literal['workspace/applyEdit']
    params: 'ApplyWorkspaceEditParams'


class CallHierarchyIncomingCallsRequest(TypedDict):
    method: Literal['callHierarchy/incomingCalls']
    params: 'CallHierarchyIncomingCallsParams'


class CallHierarchyOutgoingCallsRequest(TypedDict):
    method: Literal['callHierarchy/outgoingCalls']
    params: 'CallHierarchyOutgoingCallsParams'


class CallHierarchyPrepareRequest(TypedDict):
    method: Literal['textDocument/prepareCallHierarchy']
    params: 'CallHierarchyPrepareParams'


class CodeActionRequest(TypedDict):
    method: Literal['textDocument/codeAction']
    params: 'CodeActionParams'


class CodeActionResolveRequest(TypedDict):
    method: Literal['codeAction/resolve']
    params: 'CodeAction'


class CodeLensRefreshRequest(TypedDict):
    method: Literal['workspace/codeLens/refresh']
    params: None


class CodeLensRequest(TypedDict):
    method: Literal['textDocument/codeLens']
    params: 'CodeLensParams'


class CodeLensResolveRequest(TypedDict):
    method: Literal['codeLens/resolve']
    params: 'CodeLens'


class ColorPresentationRequest(TypedDict):
    method: Literal['textDocument/colorPresentation']
    params: 'ColorPresentationParams'


class CompletionRequest(TypedDict):
    method: Literal['textDocument/completion']
    params: 'CompletionParams'


class CompletionResolveRequest(TypedDict):
    method: Literal['completionItem/resolve']
    params: 'CompletionItem'


class ConfigurationRequest(TypedDict):
    method: Literal['workspace/configuration']
    params: 'ConfigurationParams'


class DeclarationRequest(TypedDict):
    method: Literal['textDocument/declaration']
    params: 'DeclarationParams'


class DefinitionRequest(TypedDict):
    method: Literal['textDocument/definition']
    params: 'DefinitionParams'


class DiagnosticRefreshRequest(TypedDict):
    method: Literal['workspace/diagnostic/refresh']
    params: None


class DocumentColorRequest(TypedDict):
    method: Literal['textDocument/documentColor']
    params: 'DocumentColorParams'


class DocumentDiagnosticRequest(TypedDict):
    method: Literal['textDocument/diagnostic']
    params: 'DocumentDiagnosticParams'


class DocumentFormattingRequest(TypedDict):
    method: Literal['textDocument/formatting']
    params: 'DocumentFormattingParams'


class DocumentHighlightRequest(TypedDict):
    method: Literal['textDocument/documentHighlight']
    params: 'DocumentHighlightParams'


class DocumentLinkRequest(TypedDict):
    method: Literal['textDocument/documentLink']
    params: 'DocumentLinkParams'


class DocumentLinkResolveRequest(TypedDict):
    method: Literal['documentLink/resolve']
    params: 'DocumentLink'


class DocumentOnTypeFormattingRequest(TypedDict):
    method: Literal['textDocument/onTypeFormatting']
    params: 'DocumentOnTypeFormattingParams'


class DocumentRangeFormattingRequest(TypedDict):
    method: Literal['textDocument/rangeFormatting']
    params: 'DocumentRangeFormattingParams'


class DocumentRangesFormattingRequest(TypedDict):
    method: Literal['textDocument/rangesFormatting']
    params: 'DocumentRangesFormattingParams'


class DocumentSymbolRequest(TypedDict):
    method: Literal['textDocument/documentSymbol']
    params: 'DocumentSymbolParams'


class ExecuteCommandRequest(TypedDict):
    method: Literal['workspace/executeCommand']
    params: 'ExecuteCommandParams'


class FoldingRangeRefreshRequest(TypedDict):
    method: Literal['workspace/foldingRange/refresh']
    params: None


class FoldingRangeRequest(TypedDict):
    method: Literal['textDocument/foldingRange']
    params: 'FoldingRangeParams'


class HoverRequest(TypedDict):
    method: Literal['textDocument/hover']
    params: 'HoverParams'


class ImplementationRequest(TypedDict):
    method: Literal['textDocument/implementation']
    params: 'ImplementationParams'


class InitializeRequest(TypedDict):
    method: Literal['initialize']
    params: 'InitializeParams'


class InlayHintRefreshRequest(TypedDict):
    method: Literal['workspace/inlayHint/refresh']
    params: None


class InlayHintRequest(TypedDict):
    method: Literal['textDocument/inlayHint']
    params: 'InlayHintParams'


class InlayHintResolveRequest(TypedDict):
    method: Literal['inlayHint/resolve']
    params: 'InlayHint'


class InlineCompletionRequest(TypedDict):
    method: Literal['textDocument/inlineCompletion']
    params: 'InlineCompletionParams'


class InlineValueRefreshRequest(TypedDict):
    method: Literal['workspace/inlineValue/refresh']
    params: None


class InlineValueRequest(TypedDict):
    method: Literal['textDocument/inlineValue']
    params: 'InlineValueParams'


class LinkedEditingRangeRequest(TypedDict):
    method: Literal['textDocument/linkedEditingRange']
    params: 'LinkedEditingRangeParams'


class MonikerRequest(TypedDict):
    method: Literal['textDocument/moniker']
    params: 'MonikerParams'


class PrepareRenameRequest(TypedDict):
    method: Literal['textDocument/prepareRename']
    params: 'PrepareRenameParams'


class ReferencesRequest(TypedDict):
    method: Literal['textDocument/references']
    params: 'ReferenceParams'


class RegistrationRequest(TypedDict):
    method: Literal['client/registerCapability']
    params: 'RegistrationParams'


class RenameRequest(TypedDict):
    method: Literal['textDocument/rename']
    params: 'RenameParams'


class SelectionRangeRequest(TypedDict):
    method: Literal['textDocument/selectionRange']
    params: 'SelectionRangeParams'


class SemanticTokensDeltaRequest(TypedDict):
    method: Literal['textDocument/semanticTokens/full/delta']
    params: 'SemanticTokensDeltaParams'


class SemanticTokensRangeRequest(TypedDict):
    method: Literal['textDocument/semanticTokens/range']
    params: 'SemanticTokensRangeParams'


class SemanticTokensRefreshRequest(TypedDict):
    method: Literal['workspace/semanticTokens/refresh']
    params: None


class SemanticTokensRequest(TypedDict):
    method: Literal['textDocument/semanticTokens/full']
    params: 'SemanticTokensParams'


class ShowDocumentRequest(TypedDict):
    method: Literal['window/showDocument']
    params: 'ShowDocumentParams'


class ShowMessageRequest(TypedDict):
    method: Literal['window/showMessageRequest']
    params: 'ShowMessageRequestParams'


class ShutdownRequest(TypedDict):
    method: Literal['shutdown']
    params: None


class SignatureHelpRequest(TypedDict):
    method: Literal['textDocument/signatureHelp']
    params: 'SignatureHelpParams'


class TextDocumentContentRefreshRequest(TypedDict):
    method: Literal['workspace/textDocumentContent/refresh']
    params: 'TextDocumentContentRefreshParams'


class TextDocumentContentRequest(TypedDict):
    method: Literal['workspace/textDocumentContent']
    params: 'TextDocumentContentParams'


class TypeDefinitionRequest(TypedDict):
    method: Literal['textDocument/typeDefinition']
    params: 'TypeDefinitionParams'


class TypeHierarchyPrepareRequest(TypedDict):
    method: Literal['textDocument/prepareTypeHierarchy']
    params: 'TypeHierarchyPrepareParams'


class TypeHierarchySubtypesRequest(TypedDict):
    method: Literal['typeHierarchy/subtypes']
    params: 'TypeHierarchySubtypesParams'


class TypeHierarchySupertypesRequest(TypedDict):
    method: Literal['typeHierarchy/supertypes']
    params: 'TypeHierarchySupertypesParams'


class UnregistrationRequest(TypedDict):
    method: Literal['client/unregisterCapability']
    params: 'UnregistrationParams'


class WillCreateFilesRequest(TypedDict):
    method: Literal['workspace/willCreateFiles']
    params: 'CreateFilesParams'


class WillDeleteFilesRequest(TypedDict):
    method: Literal['workspace/willDeleteFiles']
    params: 'DeleteFilesParams'


class WillRenameFilesRequest(TypedDict):
    method: Literal['workspace/willRenameFiles']
    params: 'RenameFilesParams'


class WillSaveTextDocumentWaitUntilRequest(TypedDict):
    method: Literal['textDocument/willSaveWaitUntil']
    params: 'WillSaveTextDocumentParams'


class WorkDoneProgressCreateRequest(TypedDict):
    method: Literal['window/workDoneProgress/create']
    params: 'WorkDoneProgressCreateParams'


class WorkspaceDiagnosticRequest(TypedDict):
    method: Literal['workspace/diagnostic']
    params: 'WorkspaceDiagnosticParams'


class WorkspaceFoldersRequest(TypedDict):
    method: Literal['workspace/workspaceFolders']
    params: None


class WorkspaceSymbolRequest(TypedDict):
    method: Literal['workspace/symbol']
    params: 'WorkspaceSymbolParams'


class WorkspaceSymbolResolveRequest(TypedDict):
    method: Literal['workspaceSymbol/resolve']
    params: 'WorkspaceSymbol'


ClientRequest: TypeAlias = Union[
    CallHierarchyIncomingCallsRequest,
    CallHierarchyOutgoingCallsRequest,
    CallHierarchyPrepareRequest,
    CodeActionRequest,
    CodeActionResolveRequest,
    CodeLensRequest,
    CodeLensResolveRequest,
    ColorPresentationRequest,
    CompletionRequest,
    CompletionResolveRequest,
    DeclarationRequest,
    DefinitionRequest,
    DocumentColorRequest,
    DocumentDiagnosticRequest,
    DocumentFormattingRequest,
    DocumentHighlightRequest,
    DocumentLinkRequest,
    DocumentLinkResolveRequest,
    DocumentOnTypeFormattingRequest,
    DocumentRangeFormattingRequest,
    DocumentRangesFormattingRequest,
    DocumentSymbolRequest,
    ExecuteCommandRequest,
    FoldingRangeRequest,
    HoverRequest,
    ImplementationRequest,
    InitializeRequest,
    InlayHintRequest,
    InlayHintResolveRequest,
    InlineCompletionRequest,
    InlineValueRequest,
    LinkedEditingRangeRequest,
    MonikerRequest,
    PrepareRenameRequest,
    ReferencesRequest,
    RenameRequest,
    SelectionRangeRequest,
    SemanticTokensDeltaRequest,
    SemanticTokensRangeRequest,
    SemanticTokensRequest,
    ShutdownRequest,
    SignatureHelpRequest,
    TextDocumentContentRequest,
    TypeDefinitionRequest,
    TypeHierarchyPrepareRequest,
    TypeHierarchySubtypesRequest,
    TypeHierarchySupertypesRequest,
    WillCreateFilesRequest,
    WillDeleteFilesRequest,
    WillRenameFilesRequest,
    WillSaveTextDocumentWaitUntilRequest,
    WorkspaceDiagnosticRequest,
    WorkspaceSymbolRequest,
    WorkspaceSymbolResolveRequest,
]


ServerRequest: TypeAlias = Union[
    ApplyWorkspaceEditRequest,
    CodeLensRefreshRequest,
    ConfigurationRequest,
    DiagnosticRefreshRequest,
    FoldingRangeRefreshRequest,
    InlayHintRefreshRequest,
    InlineValueRefreshRequest,
    RegistrationRequest,
    SemanticTokensRefreshRequest,
    ShowDocumentRequest,
    ShowMessageRequest,
    TextDocumentContentRefreshRequest,
    UnregistrationRequest,
    WorkDoneProgressCreateRequest,
    WorkspaceFoldersRequest,
]


class ApplyWorkspaceEditResponse(TypedDict):
    method: Literal['workspace/applyEdit']
    result: 'ApplyWorkspaceEditResult'


class CallHierarchyIncomingCallsResponse(TypedDict):
    method: Literal['callHierarchy/incomingCalls']
    result: Union[List['CallHierarchyIncomingCall'], None]


class CallHierarchyOutgoingCallsResponse(TypedDict):
    method: Literal['callHierarchy/outgoingCalls']
    result: Union[List['CallHierarchyOutgoingCall'], None]


class CallHierarchyPrepareResponse(TypedDict):
    method: Literal['textDocument/prepareCallHierarchy']
    result: Union[List['CallHierarchyItem'], None]


class CodeActionResponse(TypedDict):
    method: Literal['textDocument/codeAction']
    result: Union[List[Union['Command', 'CodeAction']], None]


class CodeActionResolveResponse(TypedDict):
    method: Literal['codeAction/resolve']
    result: 'CodeAction'


class CodeLensRefreshResponse(TypedDict):
    method: Literal['workspace/codeLens/refresh']
    result: None


class CodeLensResponse(TypedDict):
    method: Literal['textDocument/codeLens']
    result: Union[List['CodeLens'], None]


class CodeLensResolveResponse(TypedDict):
    method: Literal['codeLens/resolve']
    result: 'CodeLens'


class ColorPresentationResponse(TypedDict):
    method: Literal['textDocument/colorPresentation']
    result: List['ColorPresentation']


class CompletionResponse(TypedDict):
    method: Literal['textDocument/completion']
    result: Union[List['CompletionItem'], 'CompletionList', None]


class CompletionResolveResponse(TypedDict):
    method: Literal['completionItem/resolve']
    result: 'CompletionItem'


class ConfigurationResponse(TypedDict):
    method: Literal['workspace/configuration']
    result: List['LSPAny']


class DeclarationResponse(TypedDict):
    method: Literal['textDocument/declaration']
    result: Union['Declaration', List['DeclarationLink'], None]


class DefinitionResponse(TypedDict):
    method: Literal['textDocument/definition']
    result: Union['Definition', List['DefinitionLink'], None]


class DiagnosticRefreshResponse(TypedDict):
    method: Literal['workspace/diagnostic/refresh']
    result: None


class DocumentColorResponse(TypedDict):
    method: Literal['textDocument/documentColor']
    result: List['ColorInformation']


class DocumentDiagnosticResponse(TypedDict):
    method: Literal['textDocument/diagnostic']
    result: 'DocumentDiagnosticReport'


class DocumentFormattingResponse(TypedDict):
    method: Literal['textDocument/formatting']
    result: Union[List['TextEdit'], None]


class DocumentHighlightResponse(TypedDict):
    method: Literal['textDocument/documentHighlight']
    result: Union[List['DocumentHighlight'], None]


class DocumentLinkResponse(TypedDict):
    method: Literal['textDocument/documentLink']
    result: Union[List['DocumentLink'], None]


class DocumentLinkResolveResponse(TypedDict):
    method: Literal['documentLink/resolve']
    result: 'DocumentLink'


class DocumentOnTypeFormattingResponse(TypedDict):
    method: Literal['textDocument/onTypeFormatting']
    result: Union[List['TextEdit'], None]


class DocumentRangeFormattingResponse(TypedDict):
    method: Literal['textDocument/rangeFormatting']
    result: Union[List['TextEdit'], None]


class DocumentRangesFormattingResponse(TypedDict):
    method: Literal['textDocument/rangesFormatting']
    result: Union[List['TextEdit'], None]


class DocumentSymbolResponse(TypedDict):
    method: Literal['textDocument/documentSymbol']
    result: Union[List['SymbolInformation'], List['DocumentSymbol'], None]


class ExecuteCommandResponse(TypedDict):
    method: Literal['workspace/executeCommand']
    result: Union['LSPAny', None]


class FoldingRangeRefreshResponse(TypedDict):
    method: Literal['workspace/foldingRange/refresh']
    result: None


class FoldingRangeResponse(TypedDict):
    method: Literal['textDocument/foldingRange']
    result: Union[List['FoldingRange'], None]


class HoverResponse(TypedDict):
    method: Literal['textDocument/hover']
    result: Union['Hover', None]


class ImplementationResponse(TypedDict):
    method: Literal['textDocument/implementation']
    result: Union['Definition', List['DefinitionLink'], None]


class InitializeResponse(TypedDict):
    method: Literal['initialize']
    result: 'InitializeResult'


class InlayHintRefreshResponse(TypedDict):
    method: Literal['workspace/inlayHint/refresh']
    result: None


class InlayHintResponse(TypedDict):
    method: Literal['textDocument/inlayHint']
    result: Union[List['InlayHint'], None]


class InlayHintResolveResponse(TypedDict):
    method: Literal['inlayHint/resolve']
    result: 'InlayHint'


class InlineCompletionResponse(TypedDict):
    method: Literal['textDocument/inlineCompletion']
    result: Union['InlineCompletionList', List['InlineCompletionItem'], None]


class InlineValueRefreshResponse(TypedDict):
    method: Literal['workspace/inlineValue/refresh']
    result: None


class InlineValueResponse(TypedDict):
    method: Literal['textDocument/inlineValue']
    result: Union[List['InlineValue'], None]


class LinkedEditingRangeResponse(TypedDict):
    method: Literal['textDocument/linkedEditingRange']
    result: Union['LinkedEditingRanges', None]


class MonikerResponse(TypedDict):
    method: Literal['textDocument/moniker']
    result: Union[List['Moniker'], None]


class PrepareRenameResponse(TypedDict):
    method: Literal['textDocument/prepareRename']
    result: Union['PrepareRenameResult', None]


class ReferencesResponse(TypedDict):
    method: Literal['textDocument/references']
    result: Union[List['Location'], None]


class RegistrationResponse(TypedDict):
    method: Literal['client/registerCapability']
    result: None


class RenameResponse(TypedDict):
    method: Literal['textDocument/rename']
    result: Union['WorkspaceEdit', None]


class SelectionRangeResponse(TypedDict):
    method: Literal['textDocument/selectionRange']
    result: Union[List['SelectionRange'], None]


class SemanticTokensDeltaResponse(TypedDict):
    method: Literal['textDocument/semanticTokens/full/delta']
    result: Union['SemanticTokens', 'SemanticTokensDelta', None]


class SemanticTokensRangeResponse(TypedDict):
    method: Literal['textDocument/semanticTokens/range']
    result: Union['SemanticTokens', None]


class SemanticTokensRefreshResponse(TypedDict):
    method: Literal['workspace/semanticTokens/refresh']
    result: None


class SemanticTokensResponse(TypedDict):
    method: Literal['textDocument/semanticTokens/full']
    result: Union['SemanticTokens', None]


class ShowDocumentResponse(TypedDict):
    method: Literal['window/showDocument']
    result: 'ShowDocumentResult'


class ShowMessageResponse(TypedDict):
    method: Literal['window/showMessageRequest']
    result: Union['MessageActionItem', None]


class ShutdownResponse(TypedDict):
    method: Literal['shutdown']
    result: None


class SignatureHelpResponse(TypedDict):
    method: Literal['textDocument/signatureHelp']
    result: Union['SignatureHelp', None]


class TextDocumentContentRefreshResponse(TypedDict):
    method: Literal['workspace/textDocumentContent/refresh']
    result: None


class TextDocumentContentResponse(TypedDict):
    method: Literal['workspace/textDocumentContent']
    result: 'TextDocumentContentResult'


class TypeDefinitionResponse(TypedDict):
    method: Literal['textDocument/typeDefinition']
    result: Union['Definition', List['DefinitionLink'], None]


class TypeHierarchyPrepareResponse(TypedDict):
    method: Literal['textDocument/prepareTypeHierarchy']
    result: Union[List['TypeHierarchyItem'], None]


class TypeHierarchySubtypesResponse(TypedDict):
    method: Literal['typeHierarchy/subtypes']
    result: Union[List['TypeHierarchyItem'], None]


class TypeHierarchySupertypesResponse(TypedDict):
    method: Literal['typeHierarchy/supertypes']
    result: Union[List['TypeHierarchyItem'], None]


class UnregistrationResponse(TypedDict):
    method: Literal['client/unregisterCapability']
    result: None


class WillCreateFilesResponse(TypedDict):
    method: Literal['workspace/willCreateFiles']
    result: Union['WorkspaceEdit', None]


class WillDeleteFilesResponse(TypedDict):
    method: Literal['workspace/willDeleteFiles']
    result: Union['WorkspaceEdit', None]


class WillRenameFilesResponse(TypedDict):
    method: Literal['workspace/willRenameFiles']
    result: Union['WorkspaceEdit', None]


class WillSaveTextDocumentWaitUntilResponse(TypedDict):
    method: Literal['textDocument/willSaveWaitUntil']
    result: Union[List['TextEdit'], None]


class WorkDoneProgressCreateResponse(TypedDict):
    method: Literal['window/workDoneProgress/create']
    result: None


class WorkspaceDiagnosticResponse(TypedDict):
    method: Literal['workspace/diagnostic']
    result: 'WorkspaceDiagnosticReport'


class WorkspaceFoldersResponse(TypedDict):
    method: Literal['workspace/workspaceFolders']
    result: Union[List['WorkspaceFolder'], None]


class WorkspaceSymbolResponse(TypedDict):
    method: Literal['workspace/symbol']
    result: Union[List['SymbolInformation'], List['WorkspaceSymbol'], None]


class WorkspaceSymbolResolveResponse(TypedDict):
    method: Literal['workspaceSymbol/resolve']
    result: 'WorkspaceSymbol'


ServerResponse: TypeAlias = Union[
    CallHierarchyIncomingCallsResponse,
    CallHierarchyOutgoingCallsResponse,
    CallHierarchyPrepareResponse,
    CodeActionResponse,
    CodeActionResolveResponse,
    CodeLensResponse,
    CodeLensResolveResponse,
    ColorPresentationResponse,
    CompletionResponse,
    CompletionResolveResponse,
    DeclarationResponse,
    DefinitionResponse,
    DocumentColorResponse,
    DocumentDiagnosticResponse,
    DocumentFormattingResponse,
    DocumentHighlightResponse,
    DocumentLinkResponse,
    DocumentLinkResolveResponse,
    DocumentOnTypeFormattingResponse,
    DocumentRangeFormattingResponse,
    DocumentRangesFormattingResponse,
    DocumentSymbolResponse,
    ExecuteCommandResponse,
    FoldingRangeResponse,
    HoverResponse,
    ImplementationResponse,
    InitializeResponse,
    InlayHintResponse,
    InlayHintResolveResponse,
    InlineCompletionResponse,
    InlineValueResponse,
    LinkedEditingRangeResponse,
    MonikerResponse,
    PrepareRenameResponse,
    ReferencesResponse,
    RenameResponse,
    SelectionRangeResponse,
    SemanticTokensDeltaResponse,
    SemanticTokensRangeResponse,
    SemanticTokensResponse,
    ShutdownResponse,
    SignatureHelpResponse,
    TextDocumentContentResponse,
    TypeDefinitionResponse,
    TypeHierarchyPrepareResponse,
    TypeHierarchySubtypesResponse,
    TypeHierarchySupertypesResponse,
    WillCreateFilesResponse,
    WillDeleteFilesResponse,
    WillRenameFilesResponse,
    WillSaveTextDocumentWaitUntilResponse,
    WorkspaceDiagnosticResponse,
    WorkspaceSymbolResponse,
    WorkspaceSymbolResolveResponse,
]


ClientResponse: TypeAlias = Union[
    ApplyWorkspaceEditResponse,
    CodeLensRefreshResponse,
    ConfigurationResponse,
    DiagnosticRefreshResponse,
    FoldingRangeRefreshResponse,
    InlayHintRefreshResponse,
    InlineValueRefreshResponse,
    RegistrationResponse,
    SemanticTokensRefreshResponse,
    ShowDocumentResponse,
    ShowMessageResponse,
    TextDocumentContentRefreshResponse,
    UnregistrationResponse,
    WorkDoneProgressCreateResponse,
    WorkspaceFoldersResponse,
]


class CancelNotification(TypedDict):
    method: Literal['$/cancelRequest']
    params: 'CancelParams'


class DidChangeConfigurationNotification(TypedDict):
    method: Literal['workspace/didChangeConfiguration']
    params: 'DidChangeConfigurationParams'


class DidChangeNotebookDocumentNotification(TypedDict):
    method: Literal['notebookDocument/didChange']
    params: 'DidChangeNotebookDocumentParams'


class DidChangeTextDocumentNotification(TypedDict):
    method: Literal['textDocument/didChange']
    params: 'DidChangeTextDocumentParams'


class DidChangeWatchedFilesNotification(TypedDict):
    method: Literal['workspace/didChangeWatchedFiles']
    params: 'DidChangeWatchedFilesParams'


class DidChangeWorkspaceFoldersNotification(TypedDict):
    method: Literal['workspace/didChangeWorkspaceFolders']
    params: 'DidChangeWorkspaceFoldersParams'


class DidCloseNotebookDocumentNotification(TypedDict):
    method: Literal['notebookDocument/didClose']
    params: 'DidCloseNotebookDocumentParams'


class DidCloseTextDocumentNotification(TypedDict):
    method: Literal['textDocument/didClose']
    params: 'DidCloseTextDocumentParams'


class DidCreateFilesNotification(TypedDict):
    method: Literal['workspace/didCreateFiles']
    params: 'CreateFilesParams'


class DidDeleteFilesNotification(TypedDict):
    method: Literal['workspace/didDeleteFiles']
    params: 'DeleteFilesParams'


class DidOpenNotebookDocumentNotification(TypedDict):
    method: Literal['notebookDocument/didOpen']
    params: 'DidOpenNotebookDocumentParams'


class DidOpenTextDocumentNotification(TypedDict):
    method: Literal['textDocument/didOpen']
    params: 'DidOpenTextDocumentParams'


class DidRenameFilesNotification(TypedDict):
    method: Literal['workspace/didRenameFiles']
    params: 'RenameFilesParams'


class DidSaveNotebookDocumentNotification(TypedDict):
    method: Literal['notebookDocument/didSave']
    params: 'DidSaveNotebookDocumentParams'


class DidSaveTextDocumentNotification(TypedDict):
    method: Literal['textDocument/didSave']
    params: 'DidSaveTextDocumentParams'


class ExitNotification(TypedDict):
    method: Literal['exit']
    params: None


class InitializedNotification(TypedDict):
    method: Literal['initialized']
    params: 'InitializedParams'


class LogMessageNotification(TypedDict):
    method: Literal['window/logMessage']
    params: 'LogMessageParams'


class LogTraceNotification(TypedDict):
    method: Literal['$/logTrace']
    params: 'LogTraceParams'


class ProgressNotification(TypedDict):
    method: Literal['$/progress']
    params: 'ProgressParams'


class PublishDiagnosticsNotification(TypedDict):
    method: Literal['textDocument/publishDiagnostics']
    params: 'PublishDiagnosticsParams'


class SetTraceNotification(TypedDict):
    method: Literal['$/setTrace']
    params: 'SetTraceParams'


class ShowMessageNotification(TypedDict):
    method: Literal['window/showMessage']
    params: 'ShowMessageParams'


class TelemetryEventNotification(TypedDict):
    method: Literal['telemetry/event']
    params: 'LSPAny'


class WillSaveTextDocumentNotification(TypedDict):
    method: Literal['textDocument/willSave']
    params: 'WillSaveTextDocumentParams'


class WorkDoneProgressCancelNotification(TypedDict):
    method: Literal['window/workDoneProgress/cancel']
    params: 'WorkDoneProgressCancelParams'


ClientNotification: TypeAlias = Union[
    CancelNotification,
    DidChangeConfigurationNotification,
    DidChangeNotebookDocumentNotification,
    DidChangeTextDocumentNotification,
    DidChangeWatchedFilesNotification,
    DidChangeWorkspaceFoldersNotification,
    DidCloseNotebookDocumentNotification,
    DidCloseTextDocumentNotification,
    DidCreateFilesNotification,
    DidDeleteFilesNotification,
    DidOpenNotebookDocumentNotification,
    DidOpenTextDocumentNotification,
    DidRenameFilesNotification,
    DidSaveNotebookDocumentNotification,
    DidSaveTextDocumentNotification,
    ExitNotification,
    InitializedNotification,
    ProgressNotification,
    SetTraceNotification,
    WillSaveTextDocumentNotification,
    WorkDoneProgressCancelNotification,
]


ServerNotification: TypeAlias = Union[
    CancelNotification,
    LogMessageNotification,
    LogTraceNotification,
    ProgressNotification,
    PublishDiagnosticsNotification,
    ShowMessageNotification,
    TelemetryEventNotification,
]
