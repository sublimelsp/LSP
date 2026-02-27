from __future__ import annotations

from ...protocol import *  # For backward compatibility with LSP packages.
from functools import total_ordering
from typing import Any
from typing import Callable
from typing import Generic
from typing import TypedDict
from typing import TypeVar
from typing import Union
from typing_extensions import NotRequired
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


class ImplementationRequest(TypedDict):
    method: Literal['textDocument/implementation']
    params: 'ImplementationParams'


class TypeDefinitionRequest(TypedDict):
    method: Literal['textDocument/typeDefinition']
    params: 'TypeDefinitionParams'


class WorkspaceFoldersRequest(TypedDict):
    method: Literal['workspace/workspaceFolders']
    params: None


class ConfigurationRequest(TypedDict):
    method: Literal['workspace/configuration']
    params: 'ConfigurationParams'


class DocumentColorRequest(TypedDict):
    method: Literal['textDocument/documentColor']
    params: 'DocumentColorParams'


class ColorPresentationRequest(TypedDict):
    method: Literal['textDocument/colorPresentation']
    params: 'ColorPresentationParams'


class FoldingRangeRequest(TypedDict):
    method: Literal['textDocument/foldingRange']
    params: 'FoldingRangeParams'


class FoldingRangeRefreshRequest(TypedDict):
    method: Literal['workspace/foldingRange/refresh']
    params: None


class DeclarationRequest(TypedDict):
    method: Literal['textDocument/declaration']
    params: 'DeclarationParams'


class SelectionRangeRequest(TypedDict):
    method: Literal['textDocument/selectionRange']
    params: 'SelectionRangeParams'


class WorkDoneProgressCreateRequest(TypedDict):
    method: Literal['window/workDoneProgress/create']
    params: 'WorkDoneProgressCreateParams'


class CallHierarchyPrepareRequest(TypedDict):
    method: Literal['textDocument/prepareCallHierarchy']
    params: 'CallHierarchyPrepareParams'


class CallHierarchyIncomingCallsRequest(TypedDict):
    method: Literal['callHierarchy/incomingCalls']
    params: 'CallHierarchyIncomingCallsParams'


class CallHierarchyOutgoingCallsRequest(TypedDict):
    method: Literal['callHierarchy/outgoingCalls']
    params: 'CallHierarchyOutgoingCallsParams'


class SemanticTokensRequest(TypedDict):
    method: Literal['textDocument/semanticTokens/full']
    params: 'SemanticTokensParams'


class SemanticTokensDeltaRequest(TypedDict):
    method: Literal['textDocument/semanticTokens/full/delta']
    params: 'SemanticTokensDeltaParams'


class SemanticTokensRangeRequest(TypedDict):
    method: Literal['textDocument/semanticTokens/range']
    params: 'SemanticTokensRangeParams'


class SemanticTokensRefreshRequest(TypedDict):
    method: Literal['workspace/semanticTokens/refresh']
    params: None


class ShowDocumentRequest(TypedDict):
    method: Literal['window/showDocument']
    params: 'ShowDocumentParams'


class LinkedEditingRangeRequest(TypedDict):
    method: Literal['textDocument/linkedEditingRange']
    params: 'LinkedEditingRangeParams'


class WillCreateFilesRequest(TypedDict):
    method: Literal['workspace/willCreateFiles']
    params: 'CreateFilesParams'


class WillRenameFilesRequest(TypedDict):
    method: Literal['workspace/willRenameFiles']
    params: 'RenameFilesParams'


class WillDeleteFilesRequest(TypedDict):
    method: Literal['workspace/willDeleteFiles']
    params: 'DeleteFilesParams'


class MonikerRequest(TypedDict):
    method: Literal['textDocument/moniker']
    params: 'MonikerParams'


class TypeHierarchyPrepareRequest(TypedDict):
    method: Literal['textDocument/prepareTypeHierarchy']
    params: 'TypeHierarchyPrepareParams'


class TypeHierarchySupertypesRequest(TypedDict):
    method: Literal['typeHierarchy/supertypes']
    params: 'TypeHierarchySupertypesParams'


class TypeHierarchySubtypesRequest(TypedDict):
    method: Literal['typeHierarchy/subtypes']
    params: 'TypeHierarchySubtypesParams'


class InlineValueRequest(TypedDict):
    method: Literal['textDocument/inlineValue']
    params: 'InlineValueParams'


class InlineValueRefreshRequest(TypedDict):
    method: Literal['workspace/inlineValue/refresh']
    params: None


class InlayHintRequest(TypedDict):
    method: Literal['textDocument/inlayHint']
    params: 'InlayHintParams'


class InlayHintResolveRequest(TypedDict):
    method: Literal['inlayHint/resolve']
    params: 'InlayHint'


class InlayHintRefreshRequest(TypedDict):
    method: Literal['workspace/inlayHint/refresh']
    params: None


class DocumentDiagnosticRequest(TypedDict):
    method: Literal['textDocument/diagnostic']
    params: 'DocumentDiagnosticParams'


class WorkspaceDiagnosticRequest(TypedDict):
    method: Literal['workspace/diagnostic']
    params: 'WorkspaceDiagnosticParams'


class DiagnosticRefreshRequest(TypedDict):
    method: Literal['workspace/diagnostic/refresh']
    params: None


class InlineCompletionRequest(TypedDict):
    method: Literal['textDocument/inlineCompletion']
    params: 'InlineCompletionParams'


class TextDocumentContentRequest(TypedDict):
    method: Literal['workspace/textDocumentContent']
    params: 'TextDocumentContentParams'


class TextDocumentContentRefreshRequest(TypedDict):
    method: Literal['workspace/textDocumentContent/refresh']
    params: 'TextDocumentContentRefreshParams'


class RegistrationRequest(TypedDict):
    method: Literal['client/registerCapability']
    params: 'RegistrationParams'


class UnregistrationRequest(TypedDict):
    method: Literal['client/unregisterCapability']
    params: 'UnregistrationParams'


class InitializeRequest(TypedDict):
    method: Literal['initialize']
    params: 'InitializeParams'


class ShutdownRequest(TypedDict):
    method: Literal['shutdown']
    params: None


class ShowMessageRequest(TypedDict):
    method: Literal['window/showMessageRequest']
    params: 'ShowMessageRequestParams'


class WillSaveTextDocumentWaitUntilRequest(TypedDict):
    method: Literal['textDocument/willSaveWaitUntil']
    params: 'WillSaveTextDocumentParams'


class CompletionRequest(TypedDict):
    method: Literal['textDocument/completion']
    params: 'CompletionParams'


class CompletionResolveRequest(TypedDict):
    method: Literal['completionItem/resolve']
    params: 'CompletionItem'


class HoverRequest(TypedDict):
    method: Literal['textDocument/hover']
    params: 'HoverParams'


class SignatureHelpRequest(TypedDict):
    method: Literal['textDocument/signatureHelp']
    params: 'SignatureHelpParams'


class DefinitionRequest(TypedDict):
    method: Literal['textDocument/definition']
    params: 'DefinitionParams'


class ReferencesRequest(TypedDict):
    method: Literal['textDocument/references']
    params: 'ReferenceParams'


class DocumentHighlightRequest(TypedDict):
    method: Literal['textDocument/documentHighlight']
    params: 'DocumentHighlightParams'


class DocumentSymbolRequest(TypedDict):
    method: Literal['textDocument/documentSymbol']
    params: 'DocumentSymbolParams'


class CodeActionRequest(TypedDict):
    method: Literal['textDocument/codeAction']
    params: 'CodeActionParams'


class CodeActionResolveRequest(TypedDict):
    method: Literal['codeAction/resolve']
    params: 'CodeAction'


class WorkspaceSymbolRequest(TypedDict):
    method: Literal['workspace/symbol']
    params: 'WorkspaceSymbolParams'


class WorkspaceSymbolResolveRequest(TypedDict):
    method: Literal['workspaceSymbol/resolve']
    params: 'WorkspaceSymbol'


class CodeLensRequest(TypedDict):
    method: Literal['textDocument/codeLens']
    params: 'CodeLensParams'


class CodeLensResolveRequest(TypedDict):
    method: Literal['codeLens/resolve']
    params: 'CodeLens'


class CodeLensRefreshRequest(TypedDict):
    method: Literal['workspace/codeLens/refresh']
    params: None


class DocumentLinkRequest(TypedDict):
    method: Literal['textDocument/documentLink']
    params: 'DocumentLinkParams'


class DocumentLinkResolveRequest(TypedDict):
    method: Literal['documentLink/resolve']
    params: 'DocumentLink'


class DocumentFormattingRequest(TypedDict):
    method: Literal['textDocument/formatting']
    params: 'DocumentFormattingParams'


class DocumentRangeFormattingRequest(TypedDict):
    method: Literal['textDocument/rangeFormatting']
    params: 'DocumentRangeFormattingParams'


class DocumentRangesFormattingRequest(TypedDict):
    method: Literal['textDocument/rangesFormatting']
    params: 'DocumentRangesFormattingParams'


class DocumentOnTypeFormattingRequest(TypedDict):
    method: Literal['textDocument/onTypeFormatting']
    params: 'DocumentOnTypeFormattingParams'


class RenameRequest(TypedDict):
    method: Literal['textDocument/rename']
    params: 'RenameParams'


class PrepareRenameRequest(TypedDict):
    method: Literal['textDocument/prepareRename']
    params: 'PrepareRenameParams'


class ExecuteCommandRequest(TypedDict):
    method: Literal['workspace/executeCommand']
    params: 'ExecuteCommandParams'


class ApplyWorkspaceEditRequest(TypedDict):
    method: Literal['workspace/applyEdit']
    params: 'ApplyWorkspaceEditParams'


ClientRequest: TypeAlias = Union[
    ImplementationRequest,
    TypeDefinitionRequest,
    DocumentColorRequest,
    ColorPresentationRequest,
    FoldingRangeRequest,
    DeclarationRequest,
    SelectionRangeRequest,
    CallHierarchyPrepareRequest,
    CallHierarchyIncomingCallsRequest,
    CallHierarchyOutgoingCallsRequest,
    SemanticTokensRequest,
    SemanticTokensDeltaRequest,
    SemanticTokensRangeRequest,
    LinkedEditingRangeRequest,
    WillCreateFilesRequest,
    WillRenameFilesRequest,
    WillDeleteFilesRequest,
    MonikerRequest,
    TypeHierarchyPrepareRequest,
    TypeHierarchySupertypesRequest,
    TypeHierarchySubtypesRequest,
    InlineValueRequest,
    InlayHintRequest,
    InlayHintResolveRequest,
    DocumentDiagnosticRequest,
    WorkspaceDiagnosticRequest,
    InlineCompletionRequest,
    TextDocumentContentRequest,
    InitializeRequest,
    ShutdownRequest,
    WillSaveTextDocumentWaitUntilRequest,
    CompletionRequest,
    CompletionResolveRequest,
    HoverRequest,
    SignatureHelpRequest,
    DefinitionRequest,
    ReferencesRequest,
    DocumentHighlightRequest,
    DocumentSymbolRequest,
    CodeActionRequest,
    CodeActionResolveRequest,
    WorkspaceSymbolRequest,
    WorkspaceSymbolResolveRequest,
    CodeLensRequest,
    CodeLensResolveRequest,
    DocumentLinkRequest,
    DocumentLinkResolveRequest,
    DocumentFormattingRequest,
    DocumentRangeFormattingRequest,
    DocumentRangesFormattingRequest,
    DocumentOnTypeFormattingRequest,
    RenameRequest,
    PrepareRenameRequest,
    ExecuteCommandRequest,
]

ServerRequest: TypeAlias = Union[
    WorkspaceFoldersRequest,
    ConfigurationRequest,
    FoldingRangeRefreshRequest,
    WorkDoneProgressCreateRequest,
    SemanticTokensRefreshRequest,
    ShowDocumentRequest,
    InlineValueRefreshRequest,
    InlayHintRefreshRequest,
    DiagnosticRefreshRequest,
    TextDocumentContentRefreshRequest,
    RegistrationRequest,
    UnregistrationRequest,
    ShowMessageRequest,
    CodeLensRefreshRequest,
    ApplyWorkspaceEditRequest,
]


class ImplementationResponse(TypedDict):
    method: Literal['textDocument/implementation']
    result: 'Definition' | List['DefinitionLink'] | None


class TypeDefinitionResponse(TypedDict):
    method: Literal['textDocument/typeDefinition']
    result: 'Definition' | List['DefinitionLink'] | None


class WorkspaceFoldersResponse(TypedDict):
    method: Literal['workspace/workspaceFolders']
    result: List['WorkspaceFolder'] | None


class ConfigurationResponse(TypedDict):
    method: Literal['workspace/configuration']
    result: List['LSPAny']


class DocumentColorResponse(TypedDict):
    method: Literal['textDocument/documentColor']
    result: List['ColorInformation']


class ColorPresentationResponse(TypedDict):
    method: Literal['textDocument/colorPresentation']
    result: List['ColorPresentation']


class FoldingRangeResponse(TypedDict):
    method: Literal['textDocument/foldingRange']
    result: List['FoldingRange'] | None


class FoldingRangeRefreshResponse(TypedDict):
    method: Literal['workspace/foldingRange/refresh']
    result: None


class DeclarationResponse(TypedDict):
    method: Literal['textDocument/declaration']
    result: 'Declaration' | List['DeclarationLink'] | None


class SelectionRangeResponse(TypedDict):
    method: Literal['textDocument/selectionRange']
    result: List['SelectionRange'] | None


class WorkDoneProgressCreateResponse(TypedDict):
    method: Literal['window/workDoneProgress/create']
    result: None


class CallHierarchyPrepareResponse(TypedDict):
    method: Literal['textDocument/prepareCallHierarchy']
    result: List['CallHierarchyItem'] | None


class CallHierarchyIncomingCallsResponse(TypedDict):
    method: Literal['callHierarchy/incomingCalls']
    result: List['CallHierarchyIncomingCall'] | None


class CallHierarchyOutgoingCallsResponse(TypedDict):
    method: Literal['callHierarchy/outgoingCalls']
    result: List['CallHierarchyOutgoingCall'] | None


class SemanticTokensResponse(TypedDict):
    method: Literal['textDocument/semanticTokens/full']
    result: SemanticTokens | None


class SemanticTokensDeltaResponse(TypedDict):
    method: Literal['textDocument/semanticTokens/full/delta']
    result: SemanticTokens | SemanticTokensDelta | None


class SemanticTokensRangeResponse(TypedDict):
    method: Literal['textDocument/semanticTokens/range']
    result: SemanticTokens | None


class SemanticTokensRefreshResponse(TypedDict):
    method: Literal['workspace/semanticTokens/refresh']
    result: None


class ShowDocumentResponse(TypedDict):
    method: Literal['window/showDocument']
    result: 'ShowDocumentResult'


class LinkedEditingRangeResponse(TypedDict):
    method: Literal['textDocument/linkedEditingRange']
    result: LinkedEditingRanges | None


class WillCreateFilesResponse(TypedDict):
    method: Literal['workspace/willCreateFiles']
    result: WorkspaceEdit | None


class WillRenameFilesResponse(TypedDict):
    method: Literal['workspace/willRenameFiles']
    result: WorkspaceEdit | None


class WillDeleteFilesResponse(TypedDict):
    method: Literal['workspace/willDeleteFiles']
    result: WorkspaceEdit | None


class MonikerResponse(TypedDict):
    method: Literal['textDocument/moniker']
    result: List['Moniker'] | None


class TypeHierarchyPrepareResponse(TypedDict):
    method: Literal['textDocument/prepareTypeHierarchy']
    result: List['TypeHierarchyItem'] | None


class TypeHierarchySupertypesResponse(TypedDict):
    method: Literal['typeHierarchy/supertypes']
    result: List['TypeHierarchyItem'] | None


class TypeHierarchySubtypesResponse(TypedDict):
    method: Literal['typeHierarchy/subtypes']
    result: List['TypeHierarchyItem'] | None


class InlineValueResponse(TypedDict):
    method: Literal['textDocument/inlineValue']
    result: List['InlineValue'] | None


class InlineValueRefreshResponse(TypedDict):
    method: Literal['workspace/inlineValue/refresh']
    result: None


class InlayHintResponse(TypedDict):
    method: Literal['textDocument/inlayHint']
    result: List['InlayHint'] | None


class InlayHintResolveResponse(TypedDict):
    method: Literal['inlayHint/resolve']
    result: 'InlayHint'


class InlayHintRefreshResponse(TypedDict):
    method: Literal['workspace/inlayHint/refresh']
    result: None


class DocumentDiagnosticResponse(TypedDict):
    method: Literal['textDocument/diagnostic']
    result: 'DocumentDiagnosticReport'


class WorkspaceDiagnosticResponse(TypedDict):
    method: Literal['workspace/diagnostic']
    result: 'WorkspaceDiagnosticReport'


class DiagnosticRefreshResponse(TypedDict):
    method: Literal['workspace/diagnostic/refresh']
    result: None


class InlineCompletionResponse(TypedDict):
    method: Literal['textDocument/inlineCompletion']
    result: 'InlineCompletionList' | List['InlineCompletionItem'] | None


class TextDocumentContentResponse(TypedDict):
    method: Literal['workspace/textDocumentContent']
    result: 'TextDocumentContentResult'


class TextDocumentContentRefreshResponse(TypedDict):
    method: Literal['workspace/textDocumentContent/refresh']
    result: None


class RegistrationResponse(TypedDict):
    method: Literal['client/registerCapability']
    result: None


class UnregistrationResponse(TypedDict):
    method: Literal['client/unregisterCapability']
    result: None


class InitializeResponse(TypedDict):
    method: Literal['initialize']
    result: 'InitializeResult'


class ShutdownResponse(TypedDict):
    method: Literal['shutdown']
    result: None


class ShowMessageResponse(TypedDict):
    method: Literal['window/showMessageRequest']
    result: MessageActionItem | None


class WillSaveTextDocumentWaitUntilResponse(TypedDict):
    method: Literal['textDocument/willSaveWaitUntil']
    result: List['TextEdit'] | None


class CompletionResponse(TypedDict):
    method: Literal['textDocument/completion']
    result: List['CompletionItem'] | 'CompletionList' | None


class CompletionResolveResponse(TypedDict):
    method: Literal['completionItem/resolve']
    result: 'CompletionItem'


class HoverResponse(TypedDict):
    method: Literal['textDocument/hover']
    result: Hover | None


class SignatureHelpResponse(TypedDict):
    method: Literal['textDocument/signatureHelp']
    result: SignatureHelp | None


class DefinitionResponse(TypedDict):
    method: Literal['textDocument/definition']
    result: 'Definition' | List['DefinitionLink'] | None


class ReferencesResponse(TypedDict):
    method: Literal['textDocument/references']
    result: List['Location'] | None


class DocumentHighlightResponse(TypedDict):
    method: Literal['textDocument/documentHighlight']
    result: List['DocumentHighlight'] | None


class DocumentSymbolResponse(TypedDict):
    method: Literal['textDocument/documentSymbol']
    result: List['SymbolInformation'] | List['DocumentSymbol'] | None


class CodeActionResponse(TypedDict):
    method: Literal['textDocument/codeAction']
    result: List[Command | CodeAction] | None


class CodeActionResolveResponse(TypedDict):
    method: Literal['codeAction/resolve']
    result: 'CodeAction'


class WorkspaceSymbolResponse(TypedDict):
    method: Literal['workspace/symbol']
    result: List['SymbolInformation'] | List['WorkspaceSymbol'] | None


class WorkspaceSymbolResolveResponse(TypedDict):
    method: Literal['workspaceSymbol/resolve']
    result: 'WorkspaceSymbol'


class CodeLensResponse(TypedDict):
    method: Literal['textDocument/codeLens']
    result: List['CodeLens'] | None


class CodeLensResolveResponse(TypedDict):
    method: Literal['codeLens/resolve']
    result: 'CodeLens'


class CodeLensRefreshResponse(TypedDict):
    method: Literal['workspace/codeLens/refresh']
    result: None


class DocumentLinkResponse(TypedDict):
    method: Literal['textDocument/documentLink']
    result: List['DocumentLink'] | None


class DocumentLinkResolveResponse(TypedDict):
    method: Literal['documentLink/resolve']
    result: 'DocumentLink'


class DocumentFormattingResponse(TypedDict):
    method: Literal['textDocument/formatting']
    result: List['TextEdit'] | None


class DocumentRangeFormattingResponse(TypedDict):
    method: Literal['textDocument/rangeFormatting']
    result: List['TextEdit'] | None


class DocumentRangesFormattingResponse(TypedDict):
    method: Literal['textDocument/rangesFormatting']
    result: List['TextEdit'] | None


class DocumentOnTypeFormattingResponse(TypedDict):
    method: Literal['textDocument/onTypeFormatting']
    result: List['TextEdit'] | None


class RenameResponse(TypedDict):
    method: Literal['textDocument/rename']
    result: WorkspaceEdit | None


class PrepareRenameResponse(TypedDict):
    method: Literal['textDocument/prepareRename']
    result: PrepareRenameResult | None


class ExecuteCommandResponse(TypedDict):
    method: Literal['workspace/executeCommand']
    result: LSPAny | None


class ApplyWorkspaceEditResponse(TypedDict):
    method: Literal['workspace/applyEdit']
    result: 'ApplyWorkspaceEditResult'


ServerResponse: TypeAlias = Union[
    ImplementationResponse,
    TypeDefinitionResponse,
    DocumentColorResponse,
    ColorPresentationResponse,
    FoldingRangeResponse,
    DeclarationResponse,
    SelectionRangeResponse,
    CallHierarchyPrepareResponse,
    CallHierarchyIncomingCallsResponse,
    CallHierarchyOutgoingCallsResponse,
    SemanticTokensResponse,
    SemanticTokensDeltaResponse,
    SemanticTokensRangeResponse,
    LinkedEditingRangeResponse,
    WillCreateFilesResponse,
    WillRenameFilesResponse,
    WillDeleteFilesResponse,
    MonikerResponse,
    TypeHierarchyPrepareResponse,
    TypeHierarchySupertypesResponse,
    TypeHierarchySubtypesResponse,
    InlineValueResponse,
    InlayHintResponse,
    InlayHintResolveResponse,
    DocumentDiagnosticResponse,
    WorkspaceDiagnosticResponse,
    InlineCompletionResponse,
    TextDocumentContentResponse,
    InitializeResponse,
    ShutdownResponse,
    WillSaveTextDocumentWaitUntilResponse,
    CompletionResponse,
    CompletionResolveResponse,
    HoverResponse,
    SignatureHelpResponse,
    DefinitionResponse,
    ReferencesResponse,
    DocumentHighlightResponse,
    DocumentSymbolResponse,
    CodeActionResponse,
    CodeActionResolveResponse,
    WorkspaceSymbolResponse,
    WorkspaceSymbolResolveResponse,
    CodeLensResponse,
    CodeLensResolveResponse,
    DocumentLinkResponse,
    DocumentLinkResolveResponse,
    DocumentFormattingResponse,
    DocumentRangeFormattingResponse,
    DocumentRangesFormattingResponse,
    DocumentOnTypeFormattingResponse,
    RenameResponse,
    PrepareRenameResponse,
    ExecuteCommandResponse,
]

ClientResponse: TypeAlias = Union[
    WorkspaceFoldersResponse,
    ConfigurationResponse,
    FoldingRangeRefreshResponse,
    WorkDoneProgressCreateResponse,
    SemanticTokensRefreshResponse,
    ShowDocumentResponse,
    InlineValueRefreshResponse,
    InlayHintRefreshResponse,
    DiagnosticRefreshResponse,
    TextDocumentContentRefreshResponse,
    RegistrationResponse,
    UnregistrationResponse,
    ShowMessageResponse,
    CodeLensRefreshResponse,
    ApplyWorkspaceEditResponse,
]


class DidChangeWorkspaceFoldersNotification(TypedDict):
    method: Literal['workspace/didChangeWorkspaceFolders']
    params: 'DidChangeWorkspaceFoldersParams'


class WorkDoneProgressCancelNotification(TypedDict):
    method: Literal['window/workDoneProgress/cancel']
    params: 'WorkDoneProgressCancelParams'


class DidCreateFilesNotification(TypedDict):
    method: Literal['workspace/didCreateFiles']
    params: 'CreateFilesParams'


class DidRenameFilesNotification(TypedDict):
    method: Literal['workspace/didRenameFiles']
    params: 'RenameFilesParams'


class DidDeleteFilesNotification(TypedDict):
    method: Literal['workspace/didDeleteFiles']
    params: 'DeleteFilesParams'


class DidOpenNotebookDocumentNotification(TypedDict):
    method: Literal['notebookDocument/didOpen']
    params: 'DidOpenNotebookDocumentParams'


class DidChangeNotebookDocumentNotification(TypedDict):
    method: Literal['notebookDocument/didChange']
    params: 'DidChangeNotebookDocumentParams'


class DidSaveNotebookDocumentNotification(TypedDict):
    method: Literal['notebookDocument/didSave']
    params: 'DidSaveNotebookDocumentParams'


class DidCloseNotebookDocumentNotification(TypedDict):
    method: Literal['notebookDocument/didClose']
    params: 'DidCloseNotebookDocumentParams'


class InitializedNotification(TypedDict):
    method: Literal['initialized']
    params: 'InitializedParams'


class ExitNotification(TypedDict):
    method: Literal['exit']
    params: None


class DidChangeConfigurationNotification(TypedDict):
    method: Literal['workspace/didChangeConfiguration']
    params: 'DidChangeConfigurationParams'


class ShowMessageNotification(TypedDict):
    method: Literal['window/showMessage']
    params: 'ShowMessageParams'


class LogMessageNotification(TypedDict):
    method: Literal['window/logMessage']
    params: 'LogMessageParams'


class TelemetryEventNotification(TypedDict):
    method: Literal['telemetry/event']
    params: 'LSPAny'


class DidOpenTextDocumentNotification(TypedDict):
    method: Literal['textDocument/didOpen']
    params: 'DidOpenTextDocumentParams'


class DidChangeTextDocumentNotification(TypedDict):
    method: Literal['textDocument/didChange']
    params: 'DidChangeTextDocumentParams'


class DidCloseTextDocumentNotification(TypedDict):
    method: Literal['textDocument/didClose']
    params: 'DidCloseTextDocumentParams'


class DidSaveTextDocumentNotification(TypedDict):
    method: Literal['textDocument/didSave']
    params: 'DidSaveTextDocumentParams'


class WillSaveTextDocumentNotification(TypedDict):
    method: Literal['textDocument/willSave']
    params: 'WillSaveTextDocumentParams'


class DidChangeWatchedFilesNotification(TypedDict):
    method: Literal['workspace/didChangeWatchedFiles']
    params: 'DidChangeWatchedFilesParams'


class PublishDiagnosticsNotification(TypedDict):
    method: Literal['textDocument/publishDiagnostics']
    params: 'PublishDiagnosticsParams'


class SetTraceNotification(TypedDict):
    method: Literal['$/setTrace']  # noqa: F722
    params: 'SetTraceParams'


class LogTraceNotification(TypedDict):
    method: Literal['$/logTrace']  # noqa: F722
    params: 'LogTraceParams'


class CancelNotification(TypedDict):
    method: Literal['$/cancelRequest']  # noqa: F722
    params: 'CancelParams'


class ProgressNotification(TypedDict):
    method: Literal['$/progress']  # noqa: F722
    params: 'ProgressParams'


ClientNotification: TypeAlias = Union[
    DidChangeWorkspaceFoldersNotification,
    WorkDoneProgressCancelNotification,
    DidCreateFilesNotification,
    DidRenameFilesNotification,
    DidDeleteFilesNotification,
    DidOpenNotebookDocumentNotification,
    DidChangeNotebookDocumentNotification,
    DidSaveNotebookDocumentNotification,
    DidCloseNotebookDocumentNotification,
    InitializedNotification,
    ExitNotification,
    DidChangeConfigurationNotification,
    DidOpenTextDocumentNotification,
    DidChangeTextDocumentNotification,
    DidCloseTextDocumentNotification,
    DidSaveTextDocumentNotification,
    WillSaveTextDocumentNotification,
    DidChangeWatchedFilesNotification,
    SetTraceNotification,
    CancelNotification,
    ProgressNotification,
]

ServerNotification: TypeAlias = Union[
    ShowMessageNotification,
    LogMessageNotification,
    TelemetryEventNotification,
    PublishDiagnosticsNotification,
    LogTraceNotification,
    CancelNotification,
    ProgressNotification,
]
