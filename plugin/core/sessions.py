from __future__ import annotations
from ...protocol import ApplyWorkspaceEditParams
from ...protocol import ClientCapabilities
from ...protocol import CodeAction
from ...protocol import CodeActionKind
from ...protocol import Command
from ...protocol import CompletionItemKind
from ...protocol import CompletionItemTag
from ...protocol import ConfigurationItem
from ...protocol import ConfigurationParams
from ...protocol import Diagnostic
from ...protocol import DiagnosticServerCancellationData
from ...protocol import DiagnosticSeverity
from ...protocol import DiagnosticTag
from ...protocol import DidChangeWatchedFilesRegistrationOptions
from ...protocol import DidChangeWorkspaceFoldersParams
from ...protocol import DocumentDiagnosticReportKind
from ...protocol import DocumentLink
from ...protocol import DocumentUri
from ...protocol import ErrorCodes
from ...protocol import ExecuteCommandParams
from ...protocol import FailureHandlingKind
from ...protocol import FileEvent
from ...protocol import FileSystemWatcher
from ...protocol import FoldingRangeKind
from ...protocol import GeneralClientCapabilities
from ...protocol import InitializeError
from ...protocol import InitializeParams
from ...protocol import InitializeResult
from ...protocol import InsertTextMode
from ...protocol import Location
from ...protocol import LocationLink
from ...protocol import LogMessageParams
from ...protocol import LSPAny
from ...protocol import LSPErrorCodes
from ...protocol import LSPObject
from ...protocol import MarkupKind
from ...protocol import PrepareSupportDefaultBehavior
from ...protocol import PreviousResultId
from ...protocol import ProgressParams
from ...protocol import ProgressToken
from ...protocol import PublishDiagnosticsParams
from ...protocol import Range
from ...protocol import RegistrationParams
from ...protocol import SemanticTokenModifiers
from ...protocol import SemanticTokenTypes
from ...protocol import ShowDocumentParams
from ...protocol import ShowMessageParams
from ...protocol import ShowMessageRequestParams
from ...protocol import SignatureHelpTriggerKind
from ...protocol import SymbolKind
from ...protocol import SymbolTag
from ...protocol import TextDocumentClientCapabilities
from ...protocol import TextDocumentSyncKind
from ...protocol import TextEdit
from ...protocol import TokenFormat
from ...protocol import UnregistrationParams
from ...protocol import WatchKind
from ...protocol import WindowClientCapabilities
from ...protocol import WorkDoneProgressBegin
from ...protocol import WorkDoneProgressCreateParams
from ...protocol import WorkDoneProgressEnd
from ...protocol import WorkDoneProgressReport
from ...protocol import WorkspaceClientCapabilities
from ...protocol import WorkspaceDiagnosticParams
from ...protocol import WorkspaceDiagnosticReport
from ...protocol import WorkspaceDocumentDiagnosticReport
from ...protocol import WorkspaceEdit
from ...protocol import WorkspaceFullDocumentDiagnosticReport
from .collections import DottedDict
from .constants import RequestFlags
from .constants import MARKO_MD_PARSER_VERSION
from .constants import SEMANTIC_TOKENS_MAP
from .constants import ST_STORAGE_PATH
from .diagnostics_storage import DiagnosticsStorage
from .edit import apply_text_edits
from .edit import parse_workspace_edit
from .edit import WorkspaceChanges
from .file_watcher import DEFAULT_WATCH_KIND
from .file_watcher import file_watcher_event_type_to_lsp_file_change_type
from .file_watcher import FileWatcher
from .file_watcher import FileWatcherEvent
from .file_watcher import get_file_watcher_implementation
from .file_watcher import lsp_watch_kind_to_file_watcher_event_types
from .logging import debug
from .logging import exception_log
from .open import center_selection
from .open import open_externally
from .open import open_file
from .progress import WindowProgressReporter
from .promise import PackagedTask
from .promise import Promise
from .protocol import Error
from .protocol import Notification
from .protocol import Request
from .protocol import ResolvedCodeLens
from .protocol import Response
from .protocol import ResponseError
from .settings import client_configs
from .settings import globalprefs
from .settings import userprefs
from .transports import Transport
from .transports import TransportCallbacks
from .types import Capabilities
from .types import ClientConfig
from .types import ClientStates
from .types import debounced
from .types import diff
from .types import DocumentSelector
from .types import method_to_capability
from .types import SemanticToken
from .types import SettingsRegistration
from .types import sublime_pattern_to_glob
from .types import WORKSPACE_DIAGNOSTICS_TIMEOUT
from .typing import StrEnum
from .url import filename_to_uri
from .url import parse_uri
from .url import unparse_uri
from .version import __version__
from .views import extract_variables
from .views import get_uri_and_range_from_location
from .views import kind_contains_other_kind
from .views import MarkdownLangMap
from .views import uri_from_view
from .workspace import is_subpath_of
from .workspace import WorkspaceFolder
from abc import ABCMeta
from abc import abstractmethod
from enum import IntEnum, IntFlag
from typing import Any, Callable, Generator, List, Literal, Protocol, TypeVar, overload
from typing import cast
from typing import TYPE_CHECKING
from typing_extensions import TypeAlias, TypeGuard
from typing_extensions import deprecated
from weakref import WeakSet
import functools
import itertools
import mdpopups
import os
import sublime
import weakref


if TYPE_CHECKING:
    from .active_request import ActiveRequest


InitCallback: TypeAlias = Callable[['Session', bool], None]
T = TypeVar('T')


class ViewStateActions(IntFlag):
    NONE = 0
    SAVE = 1
    CLOSE = 2


def is_workspace_full_document_diagnostic_report(
    report: WorkspaceDocumentDiagnosticReport
) -> TypeGuard[WorkspaceFullDocumentDiagnosticReport]:
    return report['kind'] == DocumentDiagnosticReportKind.Full


def is_diagnostic_server_cancellation_data(data: Any) -> TypeGuard[DiagnosticServerCancellationData]:
    return isinstance(data, dict) and 'retriggerRequest' in data


def get_semantic_tokens_map(custom_tokens_map: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    tokens_scope_map = SEMANTIC_TOKENS_MAP.copy()
    if custom_tokens_map is not None:
        tokens_scope_map.update(custom_tokens_map)
    return tuple(sorted(tokens_scope_map.items()))  # make map hashable


@functools.lru_cache(maxsize=128)
def decode_semantic_token(
    types_legend: tuple[str, ...],
    modifiers_legend: tuple[str, ...],
    tokens_scope_map: tuple[tuple[str, str], ...],
    token_type_encoded: int,
    token_modifiers_encoded: int
) -> tuple[str, list[str], str | None]:
    """
    This function converts the token type and token modifiers from encoded numbers into names, based on the legend from
    the server. It also returns the corresponding scope name, which will be used for the highlighting color, either
    derived from a predefined scope map if the token type is one of the types defined in the LSP specs, or from a scope
    for custom token types if it was added in the client configuration (will be `None` if no scope has been defined for
    the custom token type).
    """

    token_type = types_legend[token_type_encoded]
    token_modifiers = [
        modifiers_legend[idx] for idx, val in enumerate(reversed(bin(token_modifiers_encoded)[2:])) if val == "1"
    ]
    scope = None
    tokens_scope_map_dict = dict(tokens_scope_map)  # convert hashable tokens/scope map back to dict for easy lookup
    if token_type in tokens_scope_map_dict:
        for token_modifier in token_modifiers:
            # this approach is limited to consider at most one modifier for the scope lookup
            key = f"{token_type}.{token_modifier}"
            if key in tokens_scope_map_dict:
                scope = tokens_scope_map_dict[key] + " meta.semantic-token.{}.{}.lsp".format(
                    token_type.lower(), token_modifier.lower())
                break  # first match wins (in case of multiple modifiers)
        else:
            scope = tokens_scope_map_dict[token_type]
            if token_modifiers:
                scope += f" meta.semantic-token.{token_type.lower()}.{token_modifiers[0].lower()}.lsp"
            else:
                scope += f" meta.semantic-token.{token_type.lower()}.lsp"
    return token_type, token_modifiers, scope


class Manager(metaclass=ABCMeta):
    """
    A Manager is a container of Sessions.
    """

    # Observers

    @property
    @abstractmethod
    def window(self) -> sublime.Window:
        """
        Get the window associated with this manager.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_session(self, config_name: str, file_path: str) -> Session | None:
        """
        Gets the session by name and file path.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_project_path(self, file_path: str) -> str | None:
        """
        Get the project path for the given file.
        """
        raise NotImplementedError()

    @abstractmethod
    def should_ignore_diagnostics(self, uri: DocumentUri, configuration: ClientConfig) -> str | None:
        """
        Should the diagnostics for this URI be shown in the view? Return a reason why not
        """

    # Mutators

    @abstractmethod
    def start_async(self, configuration: ClientConfig, initiating_view: sublime.View) -> None:
        """
        Start a new Session with the given configuration. The initiating view is the view that caused this method to
        be called.

        A normal flow of calls would be start -> on_post_initialize -> do language server things -> on_post_exit.
        However, it is possible that the subprocess cannot start, in which case on_post_initialize will never be called.
        """
        raise NotImplementedError()

    @abstractmethod
    def on_diagnostics_updated(self) -> None:
        raise NotImplementedError()

    # Event callbacks

    @abstractmethod
    def on_post_exit_async(self, session: Session, exit_code: int, exception: Exception | None) -> None:
        """
        The given Session has stopped with the given exit code.
        """
        raise NotImplementedError()


def _int_enum_to_list(e: type[IntEnum]) -> list[int]:
    return [v.value for v in e]


def _str_enum_to_list(e: type[StrEnum]) -> list[str]:
    return [v.value for v in e]


def get_initialize_params(variables: dict[str, str], workspace_folders: list[WorkspaceFolder],
                          config: ClientConfig) -> InitializeParams:
    completion_kinds = cast(List[CompletionItemKind], _int_enum_to_list(CompletionItemKind))
    symbol_kinds = cast(List[SymbolKind], _int_enum_to_list(SymbolKind))
    diagnostic_tag_value_set = cast(List[DiagnosticTag], _int_enum_to_list(DiagnosticTag))
    completion_tag_value_set = cast(List[CompletionItemTag], _int_enum_to_list(CompletionItemTag))
    symbol_tag_value_set = cast(List[SymbolTag], _int_enum_to_list(SymbolTag))
    semantic_token_types = cast(List[str], _str_enum_to_list(SemanticTokenTypes))
    if config.semantic_tokens is not None:
        for token_type in config.semantic_tokens.keys():
            if token_type not in semantic_token_types:
                semantic_token_types.append(token_type)
    semantic_token_modifiers = cast(List[str], _str_enum_to_list(SemanticTokenModifiers))
    supported_markup_kinds = cast(List[MarkupKind], [MarkupKind.Markdown.value, MarkupKind.PlainText.value])
    folding_range_kind_value_set = cast(List[FoldingRangeKind], _str_enum_to_list(FoldingRangeKind))
    first_folder = workspace_folders[0] if workspace_folders else None
    general_capabilities: GeneralClientCapabilities = {
        # https://microsoft.github.io/language-server-protocol/specification#regExp
        "regularExpressions": {
            # https://www.sublimetext.com/docs/completions.html#ver-dev
            # https://www.boost.org/doc/libs/1_64_0/libs/regex/doc/html/boost_regex/syntax/perl_syntax.html
            # ECMAScript syntax is a subset of Perl syntax
            "engine": "ECMAScript"
        },
        # https://microsoft.github.io/language-server-protocol/specification#markupContent
        "markdown": {
            # https://github.com/frostming/marko
            "parser": "marko",
            "version": MARKO_MD_PARSER_VERSION
        } if MARKO_MD_PARSER_VERSION else {
            # https://python-markdown.github.io
            "parser": "Python-Markdown",
            "version": mdpopups.markdown.__version__  # pyright: ignore[reportAttributeAccessIssue]

        }
    }
    text_document_capabilities: TextDocumentClientCapabilities = {
        "synchronization": {
            "dynamicRegistration": True,  # exceptional
            "didSave": True,
            "willSave": True,
            "willSaveWaitUntil": True
        },
        "hover": {
            "dynamicRegistration": True,
            "contentFormat": supported_markup_kinds
        },
        "completion": {
            "dynamicRegistration": True,
            "completionItem": {
                "snippetSupport": True,
                "deprecatedSupport": True,
                "documentationFormat": supported_markup_kinds,
                "tagSupport": {
                    "valueSet": completion_tag_value_set
                },
                "resolveSupport": {
                    "properties": ["detail", "documentation", "additionalTextEdits"]
                },
                "insertReplaceSupport": True,
                "insertTextModeSupport": {
                    "valueSet": cast(List[InsertTextMode], [InsertTextMode.AdjustIndentation.value])
                },
                "labelDetailsSupport": True,
            },
            "completionItemKind": {
                "valueSet": completion_kinds
            },
            "insertTextMode": cast(InsertTextMode, InsertTextMode.AdjustIndentation.value),
            "completionList": {
                "itemDefaults": ["editRange", "insertTextFormat", "data"]
            }
        },
        "signatureHelp": {
            "dynamicRegistration": True,
            "contextSupport": True,
            "signatureInformation": {
                "activeParameterSupport": True,
                "documentationFormat": supported_markup_kinds,
                "parameterInformation": {
                    "labelOffsetSupport": True
                }
            }
        },
        "references": {
            "dynamicRegistration": True
        },
        "documentHighlight": {
            "dynamicRegistration": True
        },
        "documentSymbol": {
            "dynamicRegistration": True,
            "hierarchicalDocumentSymbolSupport": True,
            "symbolKind": {
                "valueSet": symbol_kinds
            },
            "tagSupport": {
                "valueSet": symbol_tag_value_set
            }
        },
        "documentLink": {
            "dynamicRegistration": True,
            "tooltipSupport": True
        },
        "formatting": {
            "dynamicRegistration": True  # exceptional
        },
        "rangeFormatting": {
            "dynamicRegistration": True,
            "rangesSupport": True
        },
        "declaration": {
            "dynamicRegistration": True,
            "linkSupport": True
        },
        "definition": {
            "dynamicRegistration": True,
            "linkSupport": True
        },
        "typeDefinition": {
            "dynamicRegistration": True,
            "linkSupport": True
        },
        "implementation": {
            "dynamicRegistration": True,
            "linkSupport": True
        },
        "codeAction": {
            "dynamicRegistration": True,
            "codeActionLiteralSupport": {
                "codeActionKind": {
                    "valueSet": cast(List[CodeActionKind], [
                        CodeActionKind.QuickFix.value,
                        CodeActionKind.Refactor.value,
                        CodeActionKind.RefactorExtract.value,
                        CodeActionKind.RefactorInline.value,
                        CodeActionKind.RefactorRewrite.value,
                        CodeActionKind.SourceFixAll.value,
                        CodeActionKind.SourceOrganizeImports.value,
                    ])
                }
            },
            "dataSupport": True,
            "isPreferredSupport": True,
            "resolveSupport": {
                "properties": [
                    "edit"
                ]
            }
        },
        "rename": {
            "dynamicRegistration": True,
            "prepareSupport": True,
            "prepareSupportDefaultBehavior": cast(
                PrepareSupportDefaultBehavior, PrepareSupportDefaultBehavior.Identifier.value),
        },
        "colorProvider": {
            "dynamicRegistration": True  # exceptional
        },
        "publishDiagnostics": {
            "relatedInformation": True,
            "tagSupport": {
                "valueSet": diagnostic_tag_value_set
            },
            "versionSupport": True,
            "codeDescriptionSupport": True,
            "dataSupport": True
        },
        "diagnostic": {
            "dynamicRegistration": True,
            "relatedDocumentSupport": True
        },
        "selectionRange": {
            "dynamicRegistration": True
        },
        "foldingRange": {
            "dynamicRegistration": True,
            "foldingRangeKind": {
                "valueSet": folding_range_kind_value_set
            }
        },
        "codeLens": {
            "dynamicRegistration": True
        },
        "inlayHint": {
            "dynamicRegistration": True,
            "resolveSupport": {
                "properties": ["textEdits", "label.command"]
            }
        },
        "semanticTokens": {
            "dynamicRegistration": True,
            "requests": {
                "range": True,
                "full": {
                    "delta": True
                }
            },
            "tokenTypes": semantic_token_types,
            "tokenModifiers": semantic_token_modifiers,
            "formats": cast(List[TokenFormat], [
                TokenFormat.Relative.value
            ]),
            "overlappingTokenSupport": False,
            "multilineTokenSupport": True,
            "augmentsSyntaxTokens": True
        },
        "callHierarchy": {
            "dynamicRegistration": True
        },
        "typeHierarchy": {
            "dynamicRegistration": True
        }
    }
    workspace_capabilites: WorkspaceClientCapabilities = {
        "applyEdit": True,
        "didChangeConfiguration": {
            "dynamicRegistration": True
        },
        "executeCommand": {},
        "workspaceEdit": {
            "documentChanges": True,
            "failureHandling": cast(FailureHandlingKind, FailureHandlingKind.Abort.value),
            "changeAnnotationSupport": {
                "groupsOnLabel": False
            }
        },
        "workspaceFolders": True,
        "symbol": {
            "dynamicRegistration": True,  # exceptional
            "resolveSupport": {
                "properties": ["location.range"]
            },
            "symbolKind": {
                "valueSet": symbol_kinds
            },
            "tagSupport": {
                "valueSet": symbol_tag_value_set
            }
        },
        "configuration": True,
        "codeLens": {
            "refreshSupport": True
        },
        "inlayHint": {
            "refreshSupport": True
        },
        "semanticTokens": {
            "refreshSupport": True
        },
        "diagnostics": {
            "refreshSupport": True
        }
    }
    window_capabilities: WindowClientCapabilities = {
        "showDocument": {
            "support": True
        },
        "showMessage": {
            "messageActionItem": {
                "additionalPropertiesSupport": True
            }
        },
        "workDoneProgress": True
    }
    capabilities: ClientCapabilities = {
        "general": general_capabilities,
        "textDocument": text_document_capabilities,
        "workspace": workspace_capabilites,
        "window": window_capabilities,
    }
    if config.experimental_capabilities is not None:
        capabilities['experimental'] = cast(LSPObject, config.experimental_capabilities)
    if get_file_watcher_implementation():
        workspace_capabilites["didChangeWatchedFiles"] = {
            "dynamicRegistration": True,
            "relativePatternSupport": True
        }
    return {
        "processId": os.getpid(),
        "clientInfo": {
            "name": "Sublime Text LSP",
            "version": ".".join(map(str, __version__))
        },
        "rootUri": first_folder.uri() if first_folder else None,
        "rootPath": first_folder.path if first_folder else None,
        "workspaceFolders": [folder.to_lsp() for folder in workspace_folders] if workspace_folders else None,
        "capabilities": capabilities,
        "initializationOptions": cast(LSPAny, config.init_options.get_resolved(variables))
    }


class SessionViewProtocol(Protocol):

    @property
    def session(self) -> Session:
        ...

    @property
    def view(self) -> sublime.View:
        ...

    @property
    def listener(self) -> weakref.ref[AbstractViewListener]:
        ...

    @property
    def session_buffer(self) -> SessionBufferProtocol:
        ...

    @property
    def active_requests(self) -> dict[int, ActiveRequest]:
        ...

    def get_uri(self) -> DocumentUri | None:
        ...

    def get_language_id(self) -> str | None:
        ...

    def get_view_for_group(self, group: int) -> sublime.View | None:
        ...

    def on_capability_added_async(self, registration_id: str, capability_path: str, options: dict[str, Any]) -> None:
        ...

    def on_capability_removed_async(self, registration_id: str, discarded_capabilities: dict[str, Any]) -> None:
        ...

    def has_capability_async(self, capability_path: str) -> bool:
        ...

    def shutdown_async(self) -> None:
        ...

    def present_diagnostics_async(self, is_view_visible: bool) -> None:
        ...

    def on_request_started_async(self, request_id: int, request: Request) -> None:
        ...

    def on_request_finished_async(self, request_id: int) -> None:
        ...

    def on_request_progress(self, request_id: int, params: dict[str, Any]) -> None:
        ...

    def get_code_lenses_for_region(self, region: sublime.Region) -> list[Command]:
        ...

    def handle_code_lenses_async(self, code_lenses: list[ResolvedCodeLens]) -> None:
        ...

    def clear_code_lenses_async(self) -> None:
        ...

    def reset_show_definitions(self) -> None:
        ...

    def on_userprefs_changed_async(self) -> None:
        ...

    def get_request_flags(self) -> RequestFlags:
        ...


class SessionBufferProtocol(Protocol):

    @property
    def session(self) -> Session:
        ...

    @property
    def session_views(self) -> WeakSet[SessionViewProtocol]:
        ...

    @property
    def diagnostics(self) -> list[tuple[Diagnostic, sublime.Region]]:
        ...

    @property
    def last_synced_version(self) -> int:
        ...

    def get_uri(self) -> str | None:
        ...

    def get_language_id(self) -> str | None:
        ...

    def get_view_in_group(self, group: int) -> sublime.View:
        ...

    def register_capability_async(
        self,
        registration_id: str,
        capability_path: str,
        registration_path: str,
        options: dict[str, Any],
        suppress_requests: bool
    ) -> None:
        ...

    def unregister_capability_async(
        self,
        registration_id: str,
        capability_path: str,
        registration_path: str
    ) -> None:
        ...

    def get_capability(self, capability_path: str) -> Any | None:
        ...

    def has_capability(self, capability_path: str) -> bool:
        ...

    def on_userprefs_changed_async(self) -> None:
        ...

    def on_diagnostics_async(
        self, raw_diagnostics: list[Diagnostic], version: int, visible_session_views: set[SessionViewProtocol]
    ) -> None:
        ...

    def get_document_link_at_point(self, view: sublime.View, point: int) -> DocumentLink | None:
        ...

    def update_document_link(self, new_link: DocumentLink) -> None:
        ...

    def do_semantic_tokens_async(self, view: sublime.View) -> None:
        ...

    def set_semantic_tokens_pending_refresh(self, needs_refresh: bool = ...) -> None:
        ...

    def get_semantic_tokens(self) -> list[SemanticToken]:
        ...

    def evaluate_semantic_tokens_color_scheme_support(self, view: sublime.View) -> None:
        ...

    def do_inlay_hints_async(self, view: sublime.View) -> None:
        ...

    def set_inlay_hints_pending_refresh(self, needs_refresh: bool = ...) -> None:
        ...

    def remove_inlay_hint_phantom(self, phantom_uuid: str) -> None:
        ...

    def remove_all_inlay_hints(self) -> None:
        ...

    def do_document_diagnostic_async(self, view: sublime.View, version: int, *, forced_update: bool = ...) -> None:
        ...

    def set_document_diagnostic_pending_refresh(self, needs_refresh: bool = ...) -> None:
        ...

    def do_code_lenses_async(self, view: sublime.View) -> None:
        ...

    def set_code_lenses_pending_refresh(self, needs_refresh: bool = True) -> None:
        ...


class AbstractViewListener(metaclass=ABCMeta):

    TOTAL_ERRORS_AND_WARNINGS_STATUS_KEY = "lsp_total_errors_and_warnings"

    view = cast(sublime.View, None)
    hover_provider_count = 0

    @abstractmethod
    def session_async(self, capability: str, point: int | None = None) -> Session | None:
        raise NotImplementedError()

    @abstractmethod
    def sessions_async(self, capability: str | None = None) -> list[Session]:
        raise NotImplementedError()

    @abstractmethod
    def session_buffers_async(self, capability: str | None = None) -> list[SessionBufferProtocol]:
        raise NotImplementedError()

    @abstractmethod
    def session_views_async(self) -> list[SessionViewProtocol]:
        raise NotImplementedError()

    @abstractmethod
    def purge_changes_async(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    def trigger_on_pre_save_async(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    def on_session_initialized_async(self, session: Session) -> None:
        raise NotImplementedError()

    @abstractmethod
    def on_session_shutdown_async(self, session: Session) -> None:
        raise NotImplementedError()

    @abstractmethod
    def get_diagnostics_async(
        self, location: sublime.Region | int, max_diagnostic_severity_level: int = DiagnosticSeverity.Hint
    ) -> list[tuple[SessionBufferProtocol, list[Diagnostic]]]:
        raise NotImplementedError()

    @abstractmethod
    def on_diagnostics_updated_async(self, is_view_visible: bool) -> None:
        raise NotImplementedError()

    @abstractmethod
    def get_language_id(self) -> str:
        raise NotImplementedError()

    @abstractmethod
    def get_uri(self) -> DocumentUri:
        raise NotImplementedError()

    @overload
    def do_signature_help_async(
        self,
        trigger_kind: Literal[SignatureHelpTriggerKind.TriggerCharacter],
        trigger_char: str
    ) -> None: ...

    @overload
    def do_signature_help_async(
        self,
        trigger_kind: Literal[SignatureHelpTriggerKind.Invoked, SignatureHelpTriggerKind.ContentChange],
        trigger_char: None = None
    ) -> None: ...

    @abstractmethod
    def do_signature_help_async(self, trigger_kind: SignatureHelpTriggerKind, trigger_char: str | None = None) -> None:
        raise NotImplementedError()

    @abstractmethod
    def navigate_signature_help(self, forward: bool) -> None:
        raise NotImplementedError()

    @abstractmethod
    def on_documentation_popup_toggle(self, *, opened: bool) -> None:
        raise NotImplementedError()

    @abstractmethod
    def on_post_move_window_async(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    def get_request_flags(self, session: Session) -> RequestFlags:
        raise NotImplementedError()


class AbstractPlugin(metaclass=ABCMeta):
    """
    Inherit from this class to handle non-standard requests and notifications.
    Given a request/notification, replace the non-alphabetic characters with an underscore, and prepend it with "m_".
    This will be the name of your method.
    For instance, to implement the non-standard eslint/openDoc request, define the Python method

        def m_eslint_openDoc(self, params, request_id):
            session = self.weaksession()
            if session:
                webbrowser.open_tab(params['url'])
                session.send_response(Response(request_id, None))

    To handle the non-standard eslint/status notification, define the Python method

        def m_eslint_status(self, params):
            pass

    To understand how this works, see the __getattr__ method of the Session class.
    """

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """
        A human-friendly name. If your plugin is called "LSP-foobar", then this should return "foobar". If you also
        have your settings file called "LSP-foobar.sublime-settings", then you don't even need to re-implement the
        configuration method (see below).
        """
        raise NotImplementedError()

    @classmethod
    def configuration(cls) -> tuple[sublime.Settings, str]:
        """
        Return the Settings object that defines the "command", "languages", and optionally the "initializationOptions",
        "default_settings", "env" and "tcp_port" as the first element in the tuple, and the path to the base settings
        filename as the second element in the tuple.

        The second element in the tuple is used to handle "settings" overrides from users properly. For example, if your
        plugin is called LSP-foobar, you would return "Packages/LSP-foobar/LSP-foobar.sublime-settings".

        The "command", "initializationOptions" and "env" are subject to template string substitution. The following
        template strings are recognized:

        $file
        $file_base_name
        $file_extension
        $file_name
        $file_path
        $platform
        $project
        $project_base_name
        $project_extension
        $project_name
        $project_path

        These are just the values from window.extract_variables(). Additionally,

        $storage_path The path to the package storage (see AbstractPlugin.storage_path)
        $cache_path   sublime.cache_path()
        $temp_dir     tempfile.gettempdir()
        $home         os.path.expanduser('~')
        $port         A random free TCP-port on localhost in case "tcp_port" is set to 0. This string template can only
                      be used in the "command"

        The "command" and "env" are expanded upon starting the subprocess of the Session. The "initializationOptions"
        are expanded upon doing the initialize request. "initializationOptions" does not expand $port.

        When you're managing your own server binary, you would typically place it in sublime.cache_path(). So your
        "command" should look like this: "command": ["$cache_path/LSP-foobar/server_binary", "--stdio"]
        """
        name = cls.name()
        basename = f"LSP-{name}.sublime-settings"
        filepath = f"Packages/LSP-{name}/{basename}"
        return sublime.load_settings(basename), filepath

    @classmethod
    def is_applicable(cls, view: sublime.View, config: ClientConfig) -> bool:
        """
        Determine whether the server should run on the given view.

        The default implementation checks whether the URI scheme and the syntax scope match against the schemes and
        selector from the settings file. You can override this method for example to dynamically evaluate the applicable
        selector, or to ignore certain views even when those would match the static config. Please note that no document
        syncronization messages (textDocument/didOpen, textDocument/didChange, textDocument/didClose, etc.) are sent to
        the server for ignored views.

        This method is called when the view gets opened. To manually trigger this method again, run the
        `lsp_check_applicable` TextCommand for the given view and with a `session_name` keyword argument.

        :param      view:             The view
        :param      config:           The config
        """
        if (syntax := view.syntax()) and (selector := cls.selector(view, config).strip()):
            # TODO replace `cls.selector(view, config)` with `config.selector` after the next release
            scheme, _ = parse_uri(uri_from_view(view))
            return scheme in config.schemes and sublime.score_selector(syntax.scope, selector) > 0
        return False

    @classmethod
    @deprecated("Use `is_applicable(view, config)` instead.")
    def selector(cls, view: sublime.View, config: ClientConfig) -> str:
        return config.selector

    @classmethod
    def additional_variables(cls) -> dict[str, str] | None:
        """
        In addition to the above variables, add more variables here to be expanded.
        """
        return None

    @classmethod
    def storage_path(cls) -> str:
        """
        The storage path. Use this as your base directory to install server files. Its path is '$DATA/Package Storage'.
        You should have an additional subdirectory preferably the same name as your plugin. For instance:

        ```python
        from LSP.plugin import AbstractPlugin
        import os


        class MyPlugin(AbstractPlugin):

            @classmethod
            def name(cls) -> str:
                return "my-plugin"

            @classmethod
            def basedir(cls) -> str:
                # Do everything relative to this directory
                return os.path.join(cls.storage_path(), cls.name())
        ```
        """
        return ST_STORAGE_PATH

    @classmethod
    def needs_update_or_installation(cls) -> bool:
        """
        If this plugin manages its own server binary, then this is the place to check whether the binary needs
        an update, or whether it needs to be installed before starting the language server.
        """
        return False

    @classmethod
    def install_or_update(cls) -> None:
        """
        Do the actual update/installation of the server binary. This runs in a separate thread, so don't spawn threads
        yourself here.
        """
        pass

    @classmethod
    def can_start(cls, window: sublime.Window, initiating_view: sublime.View,
                  workspace_folders: list[WorkspaceFolder], configuration: ClientConfig) -> str | None:
        """
        Determines ability to start. This is called after needs_update_or_installation and after install_or_update.
        So you may assume that if you're managing your server binary, then it is already installed when this
        classmethod is called.

        :param      window:             The window
        :param      initiating_view:    The initiating view
        :param      workspace_folders:  The workspace folders
        :param      configuration:      The configuration

        :returns:   A string describing the reason why we should not start a language server session, or None if we
                    should go ahead and start a session.
        """
        return None

    @classmethod
    def on_pre_start(cls, window: sublime.Window, initiating_view: sublime.View,
                     workspace_folders: list[WorkspaceFolder], configuration: ClientConfig) -> str | None:
        """
        Callback invoked just before the language server subprocess is started. This is the place to do last-minute
        adjustments to your "command" or "init_options" in the passed-in "configuration" argument, or change the
        order of the workspace folders. You can also choose to return a custom working directory, but consider that a
        language server should not care about the working directory.

        :param      window:             The window
        :param      initiating_view:    The initiating view
        :param      workspace_folders:  The workspace folders, you can modify these
        :param      configuration:      The configuration, you can modify this one

        :returns:   A desired working directory, or None if you don't care
        """
        return None

    @classmethod
    def on_post_start(cls, window: sublime.Window, initiating_view: sublime.View,
                      workspace_folders: list[WorkspaceFolder], configuration: ClientConfig) -> None:
        """
        Callback invoked when the subprocess was just started.

        :param      window:             The window
        :param      initiating_view:    The initiating view
        :param      workspace_folders:  The workspace folders
        :param      configuration:      The configuration
        """
        pass

    @classmethod
    @deprecated("Use `is_applicable(view, config)` instead.")
    def should_ignore(cls, view: sublime.View) -> bool:
        return False

    @classmethod
    def markdown_language_id_to_st_syntax_map(cls) -> MarkdownLangMap | None:
        """
        Override this method to tweak the syntax highlighting of code blocks in popups from your language server.
        The returned object should be a dictionary exactly in the form of mdpopup's language_map setting.

        See: https://facelessuser.github.io/sublime-markdown-popups/settings/#mdpopupssublime_user_lang_map

        :returns:   The markdown language map, or None
        """
        return None

    def __init__(self, weaksession: weakref.ref[Session]) -> None:
        """
        Constructs a new instance. Your instance is constructed after a response to the initialize request.

        :param      weaksession:  A weak reference to the Session. You can grab a strong reference through
                                  self.weaksession(), but don't hold on to that reference.
        """
        self.weaksession = weaksession

    def on_settings_changed(self, settings: DottedDict) -> None:
        """
        Override this method to alter the settings that are returned to the server for the
        workspace/didChangeConfiguration notification and the workspace/configuration requests.

        :param      settings:      The settings that the server should receive.
        """
        pass

    def on_workspace_configuration(self, params: ConfigurationItem, configuration: Any) -> Any:
        """
        Override to augment configuration returned for the workspace/configuration request.

        :param      params:         A ConfigurationItem for which configuration is requested.
        :param      configuration:  The pre-resolved configuration for given params using the settings object or None.

        :returns: The resolved configuration for given params.
        """
        return configuration

    def on_pre_server_command(self, command: ExecuteCommandParams, done_callback: Callable[[], None]) -> bool:
        """
        Intercept a command that is about to be sent to the language server.

        :param    command:        The payload containing a "command" and optionally "arguments".
        :param    done_callback:  The callback that you promise to invoke when you return true.

        :returns: True if *YOU* will handle this command plugin-side, false otherwise. You must invoke the
                  passed `done_callback` when you're done.
        """
        return False

    def on_pre_send_request_async(self, request_id: int, request: Request) -> None:
        """
        Notifies about a request that is about to be sent to the language server.
        This API is triggered on async thread.

        :param    request_id:  The request ID.
        :param    request:     The request object. The request params can be modified by the plugin.
        """
        pass

    def on_pre_send_notification_async(self, notification: Notification) -> None:
        """
        Notifies about a notification that is about to be sent to the language server.
        This API is triggered on async thread.

        :param    notification:  The notification object. The notification params can be modified by the plugin.
        """
        pass

    def on_server_response_async(self, method: str, response: Response) -> None:
        """
        Notifies about a response message that has been received from the language server.
        Only successful responses are passed to this method.

        :param    method:    The method of the request.
        :param    response:  The response object to the request. The response.result field can be modified by the
                             plugin, before it gets further handled by the LSP package.
        """
        pass

    def on_server_notification_async(self, notification: Notification) -> None:
        """
        Notifies about a notification message that has been received from the language server.

        :param    notification:  The notification object.
        """
        pass

    def on_open_uri_async(self, uri: DocumentUri, callback: Callable[[str | None, str, str], None]) -> bool:
        """
        Called when a language server reports to open an URI. If you know how to handle this URI, then return True and
        invoke the passed-in callback some time.

        The arguments of the provided callback work as follows:

        - The first argument is the title of the view that will be populated with the content of a new scratch view.
          If `None` is passed, no new view will be opened and the other arguments are ignored.
        - The second argument is the content of the view.
        - The third argument is the syntax to apply for the new view.
        """
        return False

    def on_session_buffer_changed_async(self, session_buffer: SessionBufferProtocol) -> None:
        """
        Called when the context of the session buffer has changed or a new buffer was opened.
        """
        pass

    def on_selection_modified_async(self, session_view: SessionViewProtocol) -> None:
        """
        Called after the selection has been modified in a view (debounced).
        """
        pass

    def on_session_end_async(self, exit_code: int | None, exception: Exception | None) -> None:
        """
        Notifies about the session ending (also if the session has crashed). Provides an opportunity to clean up
        any stored state or delete references to the session or plugin instance that would otherwise prevent the
        instance from being garbage-collected.

        If the session hasn't crashed, a shutdown message will be send immediately
        after this method returns. In this case exit_code and exception are None.
        If the session has crashed, the exit_code and an optional exception are provided.

        This API is triggered on async thread.
        """
        pass


_plugins: dict[str, tuple[type[AbstractPlugin], SettingsRegistration]] = {}


def _register_plugin_impl(plugin: type[AbstractPlugin], notify_listener: bool) -> None:
    global _plugins
    name = plugin.name()
    if name in _plugins:
        return
    try:
        settings, base_file = plugin.configuration()
        if client_configs.add_external_config(name, settings, base_file, notify_listener):
            on_change = functools.partial(client_configs.update_external_config, name, settings, base_file)
            _plugins[name] = (plugin, SettingsRegistration(settings, on_change))
    except Exception as ex:
        exception_log(f'Failed to register plugin "{name}"', ex)


def register_plugin(plugin: type[AbstractPlugin], notify_listener: bool = True) -> None:
    """
    Register an LSP plugin in LSP.

    You should put a call to this function in your `plugin_loaded` callback. This way, when your package is disabled
    by a user and then re-enabled again by a user, the changes in state are picked up by LSP, and your language server
    will start for the relevant views.

    While your helper package may still work without calling `register_plugin` in `plugin_loaded`, the user will have a
    better experience when you do call this function.

    Your implementation should look something like this:

    ```python
    from LSP.plugin import register_plugin
    from LSP.plugin import unregister_plugin
    from LSP.plugin import AbstractPlugin


    class MyPlugin(AbstractPlugin):
        ...


    def plugin_loaded():
        register_plugin(MyPlugin)

    def plugin_unloaded():
        unregister_plugin(MyPlugin)
    ```

    If you need to install supplementary files (e.g. javascript source code that implements the actual server), do so
    in `AbstractPlugin.install_or_update` in a blocking manner, without the use of Python's `threading` module.
    """
    if notify_listener:
        # There is a bug in Sublime Text's `plugin_loaded` callback. When the package is in the list of
        # `"ignored_packages"` in Packages/User/Preferences.sublime-settings, and then removed from that list, the
        # sublime.Settings object has missing keys/values. To circumvent this, we run the actual registration one tick
        # later. At that point, the settings object is fully loaded. At least, it seems that way. For more context,
        # see https://github.com/sublimehq/sublime_text/issues/3379
        # and https://github.com/sublimehq/sublime_text/issues/2099
        sublime.set_timeout(lambda: _register_plugin_impl(plugin, notify_listener))
    else:
        _register_plugin_impl(plugin, notify_listener)


def unregister_plugin(plugin: type[AbstractPlugin]) -> None:
    """
    Unregister an LSP plugin in LSP.

    You should put a call to this function in your `plugin_unloaded` callback. this way, when your package is disabled
    by a user, your language server is shut down for the views that it is attached to. This results in a good user
    experience.
    """
    global _plugins
    name = plugin.name()
    try:
        _plugins.pop(name, None)
        client_configs.remove_external_config(name)
    except Exception as ex:
        exception_log(f'Failed to unregister plugin "{name}"', ex)


def get_plugin(name: str) -> type[AbstractPlugin] | None:
    global _plugins
    tup = _plugins.get(name, None)
    return tup[0] if tup else None


class Logger(metaclass=ABCMeta):

    @abstractmethod
    def stderr_message(self, message: str) -> None:
        pass

    @abstractmethod
    def outgoing_response(self, request_id: Any, params: Any) -> None:
        pass

    @abstractmethod
    def outgoing_error_response(self, request_id: Any, error: Error) -> None:
        pass

    @abstractmethod
    def outgoing_request(self, request_id: int, method: str, params: Any) -> None:
        pass

    @abstractmethod
    def outgoing_notification(self, method: str, params: Any) -> None:
        pass

    @abstractmethod
    def incoming_response(self, request_id: int | None, params: Any, is_error: bool) -> None:
        pass

    @abstractmethod
    def incoming_request(self, request_id: Any, method: str, params: Any) -> None:
        pass

    @abstractmethod
    def incoming_notification(self, method: str, params: Any, unhandled: bool) -> None:
        pass


def print_to_status_bar(error: dict[str, Any]) -> None:
    sublime.status_message(error["message"])


def method2attr(method: str) -> str:
    # window/messageRequest -> m_window_messageRequest
    # $/progress -> m___progress
    # client/registerCapability -> m_client_registerCapability
    return 'm_' + ''.join(map(lambda c: c if c.isalpha() else '_', method))


class _RegistrationData:

    __slots__ = ("registration_id", "capability_path", "registration_path", "options", "session_buffers", "selector")

    def __init__(
        self,
        registration_id: str,
        capability_path: str,
        registration_path: str,
        options: dict[str, Any]
    ) -> None:
        self.registration_id = registration_id
        self.registration_path = registration_path
        self.capability_path = capability_path
        document_selector = options.pop("documentSelector", None)
        if not isinstance(document_selector, list):
            document_selector = []
        self.selector = DocumentSelector(document_selector)
        self.options = options
        self.session_buffers: WeakSet[SessionBufferProtocol] = WeakSet()

    def __del__(self) -> None:
        for sb in self.session_buffers:
            sb.unregister_capability_async(self.registration_id, self.capability_path, self.registration_path)

    def check_applicable(self, sb: SessionBufferProtocol, *, suppress_requests: bool = False) -> None:
        for sv in sb.session_views:
            if self.selector.matches(sv.view):
                self.session_buffers.add(sb)
                sb.register_capability_async(
                    self.registration_id, self.capability_path, self.registration_path, self.options, suppress_requests)
                return


# These prefixes should disambiguate common string generation techniques like UUID4.
_WORK_DONE_PROGRESS_PREFIX = "$ublime-work-done-progress-"
_PARTIAL_RESULT_PROGRESS_PREFIX = "$ublime-partial-result-progress-"


class Session(TransportCallbacks):

    def __init__(self, manager: Manager, logger: Logger, workspace_folders: list[WorkspaceFolder],
                 config: ClientConfig, plugin_class: type[AbstractPlugin] | None) -> None:
        self.transport: Transport | None = None
        self.working_directory: str | None = None
        self.request_id = 0  # Our request IDs are always integers.
        self._logger = logger
        self._response_handlers: dict[int, tuple[Request, Callable, Callable[[Any], None]]] = {}
        self.config = config
        self.config_status_message = ''
        self.manager = weakref.ref(manager)
        self.window = manager.window
        self.state = ClientStates.STARTING
        self.capabilities = Capabilities()
        self.diagnostics = DiagnosticsStorage()
        self.diagnostics_result_ids: dict[DocumentUri, str | None] = {}
        self.workspace_diagnostics_pending_response: int | None = None
        self.exiting = False
        self._registrations: dict[str, _RegistrationData] = {}
        self._init_callback: InitCallback | None = None
        self._initialize_error: tuple[int, Exception | None] | None = None
        self._views_opened = 0
        self._workspace_folders = workspace_folders
        self._session_views: WeakSet[SessionViewProtocol] = WeakSet()
        self._session_buffers: WeakSet[SessionBufferProtocol] = WeakSet()
        self._progress: dict[ProgressToken, WindowProgressReporter | None] = {}
        self._watcher_impl = get_file_watcher_implementation()
        self._static_file_watchers: list[FileWatcher] = []
        self._dynamic_file_watchers: dict[str, list[FileWatcher]] = {}
        self._plugin_class = plugin_class
        self._plugin: AbstractPlugin | None = None
        self._status_messages: dict[str, str] = {}
        self._semantic_tokens_map = get_semantic_tokens_map(config.semantic_tokens)
        self._is_executing_refactoring_command = False
        self._logged_unsupported_commands: set[str] = set()

    def __getattr__(self, name: str) -> Any:
        """
        If we don't have a request/notification handler, look up the request/notification handler in the plugin.
        """
        if name.startswith('m_'):
            attr = getattr(self._plugin, name)
            if attr is not None:
                return attr
        raise AttributeError(name)

    # TODO: Create an assurance that the API doesn't change here as it can be used by plugins.
    def get_workspace_folders(self) -> list[WorkspaceFolder]:
        return self._workspace_folders

    def uses_plugin(self) -> bool:
        return self._plugin is not None

    @property
    def plugin(self) -> AbstractPlugin | None:
        return self._plugin

    # --- session view management --------------------------------------------------------------------------------------

    def register_session_view_async(self, sv: SessionViewProtocol) -> None:
        self._session_views.add(sv)
        self._views_opened += 1
        for status_key, message in self._status_messages.items():
            sv.view.set_status(status_key, message)

    def unregister_session_view_async(self, sv: SessionViewProtocol) -> None:
        self._session_views.discard(sv)
        if not self._session_views:
            current_count = self._views_opened
            debounced(self.end_async, 3000, lambda: self._views_opened == current_count, async_thread=True)

    def session_views_async(self) -> Generator[SessionViewProtocol, None, None]:
        """
        It is only safe to iterate over this in the async thread
        """
        yield from self._session_views

    def session_view_for_view_async(self, view: sublime.View) -> SessionViewProtocol | None:
        for sv in self.session_views_async():
            if sv.view == view:
                return sv
        return None

    def set_config_status_async(self, message: str) -> None:
        """
        Sets the message that is shown in parenthesis within the permanent language server status.

        :param message: The message
        """
        self.config_status_message = message.strip()
        self._redraw_config_status_async()

    def _redraw_config_status_async(self) -> None:
        for sv in self.session_views_async():
            self.config.set_view_status(sv.view, self.config_status_message)

    @deprecated("Use set_config_status_async(message) instead")
    def set_window_status_async(self, key: str, message: str) -> None:
        self._status_messages[key] = message
        for sv in self.session_views_async():
            sv.view.set_status(key, message)

    @deprecated("Use set_config_status_async('') instead")
    def erase_window_status_async(self, key: str) -> None:
        self._status_messages.pop(key, None)
        for sv in self.session_views_async():
            sv.view.erase_status(key)

    # --- session buffer management ------------------------------------------------------------------------------------

    def register_session_buffer_async(self, sb: SessionBufferProtocol) -> None:
        self._session_buffers.add(sb)
        for data in self._registrations.values():
            data.check_applicable(sb, suppress_requests=True)
        if (uri := sb.get_uri()) and (diagnostics := self.diagnostics.diagnostics_by_document_uri(uri)):
            self._publish_diagnostics_to_session_buffer_async(sb, diagnostics, sb.last_synced_version)

    def _publish_diagnostics_to_session_buffer_async(
        self, sb: SessionBufferProtocol, diagnostics: list[Diagnostic], version: int
    ) -> None:
        visible_session_views, _ = self.session_views_by_visibility()
        sb.on_diagnostics_async(diagnostics, version, visible_session_views)

    def unregister_session_buffer_async(self, sb: SessionBufferProtocol) -> None:
        self._session_buffers.discard(sb)

    def session_buffers_async(self) -> Generator[SessionBufferProtocol, None, None]:
        """
        It is only safe to iterate over this in the async thread
        """
        yield from self._session_buffers

    def get_session_buffer_for_uri_async(self, uri: DocumentUri) -> SessionBufferProtocol | None:
        scheme, path = parse_uri(uri)
        if scheme == "file":

            def compare_by_samefile(sb: SessionBufferProtocol | None) -> bool:
                if not sb:
                    return False
                candidate = sb.get_uri()
                if not isinstance(candidate, str):
                    return False
                candidate_scheme, candidate_path = parse_uri(candidate)
                if candidate_scheme != "file":
                    return False
                if path == candidate_path:
                    return True
                try:
                    return os.path.samefile(path, candidate_path)
                except FileNotFoundError:
                    return False

            predicate = compare_by_samefile
        else:

            def compare_by_string(sb: SessionBufferProtocol | None) -> bool:
                return sb.get_uri() == path if sb else False

            predicate = compare_by_string
        return next(filter(predicate, self.session_buffers_async()), None)

    # --- capability observers -----------------------------------------------------------------------------------------

    def can_handle(self, view: sublime.View, scheme: str, capability: str | None, inside_workspace: bool) -> bool:
        if not self.state == ClientStates.READY:
            return False
        if self._plugin and self._plugin.should_ignore(view):  # TODO remove after next release
            debug(view, "ignored by plugin", self._plugin.__class__.__name__)
            return False
        if scheme == "file":
            file_name = view.file_name()
            if not file_name:
                # We're closing down
                return False
            elif not self.handles_path(file_name, inside_workspace):
                return False
        if self.config.match_view(view, scheme):
            # If there's no capability requirement then this session can handle the view
            if capability is None:
                return True
            if sv := self.session_view_for_view_async(view):
                return sv.has_capability_async(capability)
            else:
                return self.has_capability(capability)
        return False

    def has_capability(self, capability: str, *, check_views: bool = False) -> bool:
        """
        Check whether this `Session` has the given `capability`. If `check_views` is set to `True`, this includes
        capabilities from dynamic registration restricted to certain views if at least one such view is open and matches
        the corresponding `DocumentSelector`.
        """
        value = self.get_capability(capability)
        if value is not False and value is not None:
            return True
        if check_views:
            return any(sb.has_capability(capability) for sb in self.session_buffers_async())
        return False

    def get_capability(self, capability: str) -> Any | None:
        if self.config.is_disabled_capability(capability):
            return None
        return self.capabilities.get(capability)

    def should_notify_did_open(self) -> bool:
        return self.capabilities.should_notify_did_open()

    def text_sync_kind(self) -> TextDocumentSyncKind:
        return self.capabilities.text_sync_kind()

    def should_notify_did_change_workspace_folders(self) -> bool:
        return self.capabilities.should_notify_did_change_workspace_folders()

    def should_notify_will_save(self) -> bool:
        return self.capabilities.should_notify_will_save()

    def should_notify_did_save(self) -> tuple[bool, bool]:
        return self.capabilities.should_notify_did_save()

    def should_notify_did_close(self) -> bool:
        return self.capabilities.should_notify_did_close()

    # --- FileWatcherProtocol ------------------------------------------------------------------------------------------

    def on_file_event_async(self, events: list[FileWatcherEvent]) -> None:
        changes: list[FileEvent] = []
        for event in events:
            event_type, filepath = event
            changes.append({
                'uri': filename_to_uri(filepath),
                'type': file_watcher_event_type_to_lsp_file_change_type(event_type),
            })
        self.send_notification(Notification.didChangeWatchedFiles({'changes': changes}))

    # --- misc methods -------------------------------------------------------------------------------------------------

    def on_userprefs_changed_async(self) -> None:
        self._redraw_config_status_async()
        for sb in self.session_buffers_async():
            sb.on_userprefs_changed_async()

    def markdown_language_id_to_st_syntax_map(self) -> MarkdownLangMap | None:
        return self._plugin.markdown_language_id_to_st_syntax_map() if self._plugin is not None else None

    def handles_path(self, file_path: str | None, inside_workspace: bool) -> bool:
        if self._supports_workspace_folders():
            # A workspace-aware language server handles any path, both inside and outside the workspaces.
            return True
        # buffer views or URI views
        if not file_path:
            return True
        # If we end up here then the language server is workspace-unaware. This means there can be more than one
        # language server with the same config name. So we have to actually do the subpath checks.
        if not self._workspace_folders or not inside_workspace:
            return True
        for folder in self._workspace_folders:
            if is_subpath_of(file_path, folder.path):
                return True
        return False

    def update_folders(self, folders: list[WorkspaceFolder]) -> None:
        if self.should_notify_did_change_workspace_folders():
            added, removed = diff(self._workspace_folders, folders)
            if added or removed:
                params: DidChangeWorkspaceFoldersParams = {
                    "event": {
                        "added": [a.to_lsp() for a in added],
                        "removed": [r.to_lsp() for r in removed]
                    }
                }
                self.send_notification(Notification.didChangeWorkspaceFolders(params))
        if self._supports_workspace_folders():
            self._workspace_folders = folders
        else:
            self._workspace_folders = folders[:1]

    def initialize_async(
        self,
        variables: dict[str, str],
        working_directory: str | None,
        transport: Transport,
        init_callback: InitCallback
    ) -> None:
        self.transport = transport
        self.working_directory = working_directory
        params = get_initialize_params(variables, self._workspace_folders, self.config)
        self._init_callback = init_callback
        self.send_request_async(
            Request.initialize(params), self._handle_initialize_success, self._handle_initialize_error)

    def _handle_initialize_success(self, result: InitializeResult) -> None:
        self.capabilities.assign(result.get('capabilities', dict()))
        if self._workspace_folders and not self._supports_workspace_folders():
            self._workspace_folders = self._workspace_folders[:1]
        self.state = ClientStates.READY
        if self._plugin_class is not None:
            self._plugin = self._plugin_class(weakref.ref(self))
            # We've missed calling the "on_server_response_async" API as plugin was not created yet.
            # Handle it now and use fake request ID since it shouldn't matter.
            self._plugin.on_server_response_async('initialize', Response(-1, result))
        self.send_notification(Notification.initialized())
        self._maybe_send_did_change_configuration()
        if execute_commands := self.get_capability('executeCommandProvider.commands'):
            debug(f"{self.config.name}: Supported execute commands: {execute_commands}")
        if code_action_kinds := self.get_capability('codeActionProvider.codeActionKinds'):
            debug(f'{self.config.name}: supported code action kinds: {code_action_kinds}')
        if semantic_token_types := self.get_capability('semanticTokensProvider.legend.tokenTypes'):
            debug(f'{self.config.name}: Supported semantic token types: {semantic_token_types}')
        if semantic_token_modifiers := self.get_capability('semanticTokensProvider.legend.tokenModifiers'):
            debug(f'{self.config.name}: Supported semantic token modifiers: {semantic_token_modifiers}')
        if self._watcher_impl:
            config = self.config.file_watcher
            if patterns := config.get('patterns'):
                events = config.get('events') or ['create', 'change', 'delete']
                for folder in self.get_workspace_folders():
                    ignores = config.get('ignores') or self._get_global_ignore_globs(folder.path)
                    watcher = self._watcher_impl.create(folder.path, patterns, events, ignores, self)
                    self._static_file_watchers.append(watcher)
        if self._init_callback:
            self._init_callback(self, False)
            self._init_callback = None
        if self.config.diagnostics_mode == "workspace" and \
                self.has_capability('diagnosticProvider.workspaceDiagnostics'):
            self.do_workspace_diagnostics_async()

    def _handle_initialize_error(self, result: InitializeError) -> None:
        self._initialize_error = (result.get('code', -1), Exception(result.get('message', 'Error initializing server')))
        # Init callback called after transport is closed to avoid pre-mature GC of Session.
        self.end_async()

    def _get_global_ignore_globs(self, root_path: str) -> list[str]:
        folder_exclude_patterns = cast(List[str], globalprefs().get('folder_exclude_patterns'))
        folder_excludes = [
            sublime_pattern_to_glob(pattern, is_directory_pattern=True, root_path=root_path)
            for pattern in folder_exclude_patterns
        ]
        file_exclude_patterns = cast(List[str], globalprefs().get('file_exclude_patterns'))
        file_excludes = [
            sublime_pattern_to_glob(pattern, is_directory_pattern=False, root_path=root_path)
            for pattern in file_exclude_patterns
        ]
        return folder_excludes + file_excludes + ['**/node_modules/**']

    def call_manager(self, method: str, *args: Any) -> None:
        if mgr := self.manager():
            getattr(mgr, method)(*args)

    def on_stderr_message(self, message: str) -> None:
        self.call_manager('handle_stderr_log', self, message)
        self._logger.stderr_message(message)

    def _supports_workspace_folders(self) -> bool:
        return self.has_capability("workspace.workspaceFolders.supported")

    def _maybe_send_did_change_configuration(self) -> None:
        if self.config.settings:
            if self._plugin:
                self._plugin.on_settings_changed(self.config.settings)
            variables = self._template_variables()
            resolved = self.config.settings.get_resolved(variables)
            self.send_notification(Notification("workspace/didChangeConfiguration", {"settings": resolved}))

    def _template_variables(self) -> dict[str, str]:
        variables = extract_variables(self.window)
        if self._plugin_class is not None:
            if extra_vars := self._plugin_class.additional_variables():
                variables.update(extra_vars)
        return variables

    def execute_command(
        self, command: ExecuteCommandParams, *, progress: bool = False, view: sublime.View | None = None,
        is_refactoring: bool = False,
    ) -> Promise:
        """Run a command from any thread. Your .then() continuations will run in Sublime's worker thread."""
        if self._plugin:
            task: PackagedTask[None] = Promise.packaged_task()
            promise, resolve = task
            if self._plugin.on_pre_server_command(command, lambda: resolve(None)):
                return promise
        command_name = command['command']
        # Handle VSCode-specific command for triggering AC/sighelp
        if command_name == "editor.action.triggerSuggest" and view:
            # Triggered from set_timeout as suggestions popup doesn't trigger otherwise.
            sublime.set_timeout(lambda: view.run_command("auto_complete"))
            return Promise.resolve(None)
        if command_name == "editor.action.triggerParameterHints" and view:

            def run_async() -> None:
                session_view = self.session_view_for_view_async(view)
                if not session_view:
                    return
                listener = session_view.listener()
                if not listener:
                    return
                listener.do_signature_help_async(SignatureHelpTriggerKind.Invoked)

            sublime.set_timeout_async(run_async)
            return Promise.resolve(None)
        # TODO: Our Promise class should be able to handle errors/exceptions
        execute_command = Promise(
            lambda resolve: self.send_request(
                Request("workspace/executeCommand", command, None, progress),
                resolve,
                lambda err: resolve(Error(err["code"], err["message"], err.get("data")))
            )
        )
        if is_refactoring:
            self._is_executing_refactoring_command = True
            execute_command.then(lambda _: self._reset_is_executing_refactoring_command())
        return execute_command

    def _reset_is_executing_refactoring_command(self) -> None:
        self._is_executing_refactoring_command = False

    def check_log_unsupported_command(self, command: str) -> None:
        if userprefs().log_debug and command not in self._logged_unsupported_commands:
            self._logged_unsupported_commands.add(command)
            debug(f'{self.config.name}: unsupported command: {command}')

    def run_code_action_async(
        self, code_action: Command | CodeAction, progress: bool, view: sublime.View | None = None
    ) -> Promise:
        command = code_action.get("command")
        if isinstance(command, str):
            code_action = cast(Command, code_action)
            # This is actually a command.
            command_params: ExecuteCommandParams = {'command': command}
            arguments = code_action.get('arguments', None)
            if isinstance(arguments, list):
                command_params['arguments'] = arguments
            is_refactoring = kind_contains_other_kind(CodeActionKind.Refactor, code_action.get('kind', ''))
            return self.execute_command(command_params, progress=progress, view=view, is_refactoring=is_refactoring)
        # At this point it cannot be a command anymore, it has to be a proper code action.
        # A code action can have an edit and/or command. Note that it can have *both*. In case both are present, we
        # must apply the edits before running the command.
        code_action = cast(CodeAction, code_action)
        return self._maybe_resolve_code_action(code_action, view) \
            .then(lambda code_action: self._apply_code_action_async(code_action, view))

    def try_open_uri_async(
        self,
        uri: DocumentUri,
        r: Range | None = None,
        flags: sublime.NewFileFlags = sublime.NewFileFlags.NONE,
        group: int = -1
    ) -> Promise[sublime.View | None] | None:
        if uri.startswith("file:"):
            return self._open_file_uri_async(uri, r, flags, group)
        # Try to find a pre-existing session-buffer
        if sb := self.get_session_buffer_for_uri_async(uri):
            view = sb.get_view_in_group(group)
            self.window.focus_view(view)
            if r:
                center_selection(view, r)
            return Promise.resolve(view)
        if uri.startswith('untitled:'):  # VSCode specific URI scheme for unsaved buffers
            if name := uri[len('untitled:'):]:
                # Check if there is a pre-existing unsaved buffer with the given name
                for view in self.window.views():
                    if view.file_name() is None and view.name() == name:
                        self.window.focus_view(view)
                        return Promise.resolve(view)
                view = self.window.new_file()
                view.set_scratch(True)
                view.set_name(name)
                return Promise.resolve(view)
            view = self.window.new_file()
            view.set_scratch(True)
            return Promise.resolve(view)
        # There is no pre-existing session-buffer, so we have to go through AbstractPlugin.on_open_uri_async.
        if self._plugin:
            return self._open_uri_with_plugin_async(self._plugin, uri, r, flags, group)
        return None

    def open_uri_async(
        self,
        uri: DocumentUri,
        r: Range | None = None,
        flags: sublime.NewFileFlags = sublime.NewFileFlags.NONE,
        group: int = -1
    ) -> Promise[sublime.View | None]:
        promise = self.try_open_uri_async(uri, r, flags, group)
        return Promise.resolve(None) if promise is None else promise

    def _open_file_uri_async(
        self,
        uri: DocumentUri,
        r: Range | None = None,
        flags: sublime.NewFileFlags = sublime.NewFileFlags.NONE,
        group: int = -1
    ) -> Promise[sublime.View | None]:
        result: PackagedTask[sublime.View | None] = Promise.packaged_task()

        def handle_continuation(view: sublime.View | None) -> None:
            if view and r:
                center_selection(view, r)
            sublime.set_timeout_async(lambda: result[1](view))

        sublime.set_timeout(lambda: open_file(self.window, uri, flags, group).then(handle_continuation))
        return result[0]

    def _open_uri_with_plugin_async(
        self,
        plugin: AbstractPlugin,
        uri: DocumentUri,
        r: Range | None,
        flags: sublime.NewFileFlags,
        group: int,
    ) -> Promise[sublime.View | None] | None:
        # I cannot type-hint an unpacked tuple
        pair: PackagedTask[tuple[str | None, str, str]] = Promise.packaged_task()
        # It'd be nice to have automatic tuple unpacking continuations
        callback = lambda a, b, c: pair[1]((a, b, c))  # noqa: E731
        if plugin.on_open_uri_async(uri, callback):
            result: PackagedTask[sublime.View | None] = Promise.packaged_task()

            def maybe_open_scratch_buffer(title: str | None, content: str, syntax: str) -> None:
                if title is not None:
                    if group > -1:
                        self.window.focus_group(group)
                    view = self.window.new_file(syntax=syntax, flags=flags)
                    # Note: the __init__ of ViewEventListeners is invoked in the next UI frame, so we can fill in the
                    # settings object here at our leisure.
                    view.settings().set("lsp_uri", uri)
                    view.set_scratch(True)
                    view.set_name(title)
                    view.run_command("append", {"characters": content})
                    view.set_read_only(True)
                    if r:
                        center_selection(view, r)
                    sublime.set_timeout_async(lambda: result[1](view))
                else:
                    sublime.set_timeout_async(lambda: result[1](None))

            pair[0].then(lambda tup: sublime.set_timeout(lambda: maybe_open_scratch_buffer(*tup)))
            return result[0]
        return None

    def open_location_async(
        self,
        location: Location | LocationLink,
        flags: sublime.NewFileFlags = sublime.NewFileFlags.NONE,
        group: int = -1
    ) -> Promise[sublime.View | None]:
        uri, r = get_uri_and_range_from_location(location)
        return self.open_uri_async(uri, r, flags, group)

    def notify_plugin_on_session_buffer_change(self, session_buffer: SessionBufferProtocol) -> None:
        if self._plugin:
            self._plugin.on_session_buffer_changed_async(session_buffer)

    def _maybe_resolve_code_action(
        self, code_action: CodeAction, view: sublime.View | None
    ) -> Promise[CodeAction | Error]:
        if "edit" not in code_action:
            has_capability = self.has_capability("codeActionProvider.resolveProvider")
            if not has_capability and view:
                if session_view := self.session_view_for_view_async(view):
                    has_capability = session_view.has_capability_async("codeActionProvider.resolveProvider")
            if has_capability:
                # We must first resolve the command and edit properties, because they can potentially be absent.
                request = Request("codeAction/resolve", code_action)
                return self.send_request_task(request)
        return Promise.resolve(code_action)

    def _apply_code_action_async(
        self, code_action: CodeAction | Error | None, view: sublime.View | None
    ) -> Promise[None]:
        if not code_action:
            return Promise.resolve(None)
        if isinstance(code_action, Error):
            # TODO: our promise must be able to handle exceptions (or, wait until we can use coroutines)
            self.window.status_message(f"Failed to apply code action: {code_action}")
            return Promise.resolve(None)
        title = code_action['title']
        edit = code_action.get("edit")
        is_refactoring = kind_contains_other_kind(CodeActionKind.Refactor, code_action.get('kind', ''))
        promise = self.apply_workspace_edit_async(edit, label=title, is_refactoring=is_refactoring) if edit else \
            Promise.resolve(None)
        command = code_action.get("command")
        if command is not None:
            execute_command: ExecuteCommandParams = {
                "command": command["command"],
            }
            arguments = command.get("arguments")
            if arguments is not None:
                execute_command['arguments'] = arguments
            return promise.then(lambda _: self.execute_command(execute_command, progress=False, view=view,
                                                               is_refactoring=is_refactoring))
        return promise

    def apply_workspace_edit_async(
        self, edit: WorkspaceEdit, *, label: str | None = None, is_refactoring: bool = False
    ) -> Promise[None]:
        """
        Apply workspace edits, and return a promise that resolves on the async thread again after the edits have been
        applied.
        """
        is_refactoring = self._is_executing_refactoring_command or is_refactoring
        return self.apply_parsed_workspace_edits(parse_workspace_edit(edit, label), is_refactoring)

    def apply_parsed_workspace_edits(self, changes: WorkspaceChanges, is_refactoring: bool = False) -> Promise[None]:
        def handle_view(
            edits: list[TextEdit],
            label: str | None,
            view_version: int | None,
            uri: str,
            view_state_actions: ViewStateActions,
            view: sublime.View | None,
        ) -> Promise[None]:
            if view is None:
                print(f'LSP: ignoring edits due to no view for uri: {uri}')
                return Promise.resolve(None)
            return apply_text_edits(view, edits, label=label, required_view_version=view_version) \
                .then(lambda view: self._set_view_state(view_state_actions, view) if view else None)

        active_sheet = self.window.active_sheet()
        selected_sheets = self.window.selected_sheets()
        promises: list[Promise[None]] = []
        auto_save = userprefs().refactoring_auto_save if is_refactoring else 'never'
        for uri, (edits, label, view_version) in changes.items():
            view_state_actions = self._get_view_state_actions(uri, auto_save)
            promises.append(
                self.open_uri_async(uri)
                    .then(functools.partial(handle_view, edits, label, view_version, uri, view_state_actions))
            )
        return Promise.all(promises) \
            .then(lambda _: self._set_selected_sheets(selected_sheets)) \
            .then(lambda _: self._set_focused_sheet(active_sheet))

    def _get_view_state_actions(self, uri: DocumentUri, auto_save: str) -> ViewStateActions:
        """
        Determine the required actions for a view after applying a WorkspaceEdit, depending on the
        "refactoring_auto_save" user setting. Returns a bitwise combination of ViewStateActions.Save and
        ViewStateActions.Close, or 0 if no action is necessary.
        """
        if auto_save == 'never':
            return ViewStateActions.NONE  # Never save or close automatically
        scheme, filepath = parse_uri(uri)
        if scheme != 'file':
            return ViewStateActions.NONE  # Can't save or close unsafed buffers (and other schemes) without user dialog
        if view := self.window.find_open_file(filepath):
            is_opened = True
            is_dirty = view.is_dirty()
        else:
            is_opened = False
            is_dirty = False
        actions = ViewStateActions.NONE
        if auto_save == 'always':
            actions |= ViewStateActions.SAVE  # Always save
            if not is_opened:
                actions |= ViewStateActions.CLOSE  # Close if file was previously closed
        elif auto_save == 'preserve':
            if not is_dirty:
                actions |= ViewStateActions.SAVE  # Only save if file didn't have unsaved changes
            if not is_opened:
                actions |= ViewStateActions.CLOSE  # Close if file was previously closed
        elif auto_save == 'preserve_opened':
            if is_opened and not is_dirty:
                # Only save if file was already open and didn't have unsaved changes, but never close
                actions |= ViewStateActions.SAVE
        return actions

    def _set_view_state(self, actions: ViewStateActions, view: sublime.View) -> Promise[None]:
        promise = Promise.resolve(None)
        should_save = bool(actions & ViewStateActions.SAVE)
        should_close = bool(actions & ViewStateActions.CLOSE)
        if should_save and view.is_dirty():
            # The save operation must be blocking in case the tab should be closed afterwards
            view.run_command('save', {'async': not should_close, 'quiet': True})
            # Allow async thread to process save notifications before closing the file or the method returns.
            promise = Promise(lambda resolve: sublime.set_timeout_async(lambda: resolve(None)))

        def handle_close() -> None:
            if should_close and not view.is_dirty():
                view.close()

        return promise.then(lambda _: handle_close())

    def _set_selected_sheets(self, sheets: list[sublime.Sheet]) -> None:
        if len(sheets) > 1 and len(self.window.selected_sheets()) != len(sheets):
            self.window.select_sheets(sheets)

    def _set_focused_sheet(self, sheet: sublime.Sheet | None) -> None:
        if sheet and sheet != self.window.active_sheet():
            self.window.focus_sheet(sheet)

    def decode_semantic_token(
        self,
        types_legend: tuple[str, ...],
        modifiers_legend: tuple[str, ...],
        token_type_encoded: int,
        token_modifiers_encoded: int
    ) -> tuple[str, list[str], str | None]:
        return decode_semantic_token(
            types_legend, modifiers_legend, self._semantic_tokens_map, token_type_encoded, token_modifiers_encoded)

    def session_views_by_visibility(self) -> tuple[set[SessionViewProtocol], set[SessionViewProtocol]]:
        visible_session_views: set[SessionViewProtocol] = set()
        not_visible_session_views: set[SessionViewProtocol] = set()
        selected_sheets: set[sublime.Sheet] = set()
        for group in range(self.window.num_groups()):
            selected_sheets = selected_sheets.union(self.window.selected_sheets_in_group(group))
        for sheet in self.window.sheets():
            view = sheet.view()
            if not view:
                continue
            sv = self.session_view_for_view_async(view)
            if not sv:
                continue
            if sheet in selected_sheets:
                visible_session_views.add(sv)
            else:
                not_visible_session_views.add(sv)
        return visible_session_views, not_visible_session_views

    # --- Workspace Pull Diagnostics -----------------------------------------------------------------------------------

    def do_workspace_diagnostics_async(self) -> None:
        if self.workspace_diagnostics_pending_response:
            # The server is probably leaving the request open intentionally, in order to continuously stream updates via
            # $/progress notifications.
            return
        previous_result_ids: list[PreviousResultId] = [
            {'uri': uri, 'value': result_id} for uri, result_id in self.diagnostics_result_ids.items()
            if result_id is not None
        ]
        params: WorkspaceDiagnosticParams = {'previousResultIds': previous_result_ids}
        if identifier := self.get_capability("diagnosticProvider.identifier"):
            params['identifier'] = identifier
        self.workspace_diagnostics_pending_response = self.send_request_async(
            Request.workspaceDiagnostic(params),
            self._on_workspace_diagnostics_async,
            self._on_workspace_diagnostics_error_async)

    def _on_workspace_diagnostics_async(
        self, response: WorkspaceDiagnosticReport, reset_pending_response: bool = True
    ) -> None:
        if reset_pending_response:
            self.workspace_diagnostics_pending_response = None
        if not response['items']:
            return
        window = sublime.active_window()
        active_view = window.active_view() if window else None
        active_view_path = active_view.file_name() if active_view else None
        for diagnostic_report in response['items']:
            uri = diagnostic_report['uri']
            # Normalize URI
            scheme, path = parse_uri(uri)
            if scheme == 'file':
                # Skip for active view
                if path == active_view_path:
                    continue
                uri = unparse_uri((scheme, path))
            # Note: 'version' is a mandatory field, but some language servers have serialization bugs with null values.
            version = diagnostic_report.get('version')
            # Skip if outdated
            # Note: this is just a necessary, but not a sufficient condition to decide whether the diagnostics for this
            # file are likely not accurate anymore, because changes in another file in the meanwhile could have affected
            # the diagnostics in this file. If this is the case, a new request is already queued, or updated partial
            # results are expected to be streamed by the server.
            if isinstance(version, int):
                sb = self.get_session_buffer_for_uri_async(uri)
                if sb and sb.last_synced_version != version:
                    continue
            self.diagnostics_result_ids[uri] = diagnostic_report.get('resultId')
            if is_workspace_full_document_diagnostic_report(diagnostic_report):
                self.m_textDocument_publishDiagnostics({'uri': uri, 'diagnostics': diagnostic_report['items']})

    def _on_workspace_diagnostics_error_async(self, error: ResponseError) -> None:
        if error['code'] == LSPErrorCodes.ServerCancelled:
            data = error.get('data')
            if is_diagnostic_server_cancellation_data(data) and data['retriggerRequest']:
                # Retrigger the request after a short delay, but don't reset the pending response variable for this
                # moment, to prevent new requests of this type in the meanwhile. The delay is used in order to prevent
                # infinite cycles of cancel -> retrigger, in case the server is busy.

                def _retrigger_request() -> None:
                    self.workspace_diagnostics_pending_response = None
                    self.do_workspace_diagnostics_async()

                sublime.set_timeout_async(_retrigger_request, WORKSPACE_DIAGNOSTICS_TIMEOUT)
                return
        self.workspace_diagnostics_pending_response = None

    # --- server request handlers --------------------------------------------------------------------------------------

    def m_window_showMessageRequest(self, params: ShowMessageRequestParams, request_id: Any) -> None:
        """handles the window/showMessageRequest request"""
        self.call_manager('handle_message_request', self, params, request_id)

    def m_window_showMessage(self, params: ShowMessageParams) -> None:
        """handles the window/showMessage notification"""
        self.call_manager('handle_show_message', self, params)

    def m_window_logMessage(self, params: LogMessageParams) -> None:
        """handles the window/logMessage notification"""
        self.call_manager('handle_log_message', self, params)

    def m_workspace_workspaceFolders(self, params: None, request_id: Any) -> None:
        """handles the workspace/workspaceFolders request"""
        self.send_response(Response(request_id, [wf.to_lsp() for wf in self._workspace_folders]))

    def m_workspace_configuration(self, params: ConfigurationParams, request_id: Any) -> None:
        """handles the workspace/configuration request"""
        items: list[Any] = []
        requested_items = params.get("items") or []
        for requested_item in requested_items:
            configuration = self.config.settings.copy(requested_item.get('section') or None)
            if self._plugin:
                items.append(self._plugin.on_workspace_configuration(requested_item, configuration))
            else:
                items.append(configuration)
        self.send_response(Response(request_id, sublime.expand_variables(items, self._template_variables())))

    def m_workspace_applyEdit(self, params: ApplyWorkspaceEditParams, request_id: Any) -> None:
        """handles the workspace/applyEdit request"""
        self.apply_workspace_edit_async(params.get('edit', {}), label=params.get('label')) \
            .then(lambda _: self.send_response(Response(request_id, {"applied": True})))

    def m_workspace_codeLens_refresh(self, params: None, request_id: Any) -> None:
        """handles the workspace/codeLens/refresh request"""
        self.send_response(Response(request_id, None))
        visible_session_views, not_visible_session_views = self.session_views_by_visibility()
        for sv in visible_session_views:
            sv.session_buffer.do_code_lenses_async(sv.view)
        for sv in not_visible_session_views:
            sv.session_buffer.set_code_lenses_pending_refresh()

    def m_workspace_semanticTokens_refresh(self, params: None, request_id: Any) -> None:
        """handles the workspace/semanticTokens/refresh request"""
        self.send_response(Response(request_id, None))
        visible_session_views, not_visible_session_views = self.session_views_by_visibility()
        for sv in visible_session_views:
            if sv.get_request_flags() & RequestFlags.SEMANTIC_TOKENS:
                sv.session_buffer.do_semantic_tokens_async(sv.view)
            else:
                sv.session_buffer.set_semantic_tokens_pending_refresh()
        for sv in not_visible_session_views:
            sv.session_buffer.set_semantic_tokens_pending_refresh()

    def m_workspace_inlayHint_refresh(self, params: None, request_id: Any) -> None:
        """handles the workspace/inlayHint/refresh request"""
        self.send_response(Response(request_id, None))
        visible_session_views, not_visible_session_views = self.session_views_by_visibility()
        for sv in visible_session_views:
            if sv.get_request_flags() & RequestFlags.INLAY_HINT:
                sv.session_buffer.do_inlay_hints_async(sv.view)
            else:
                sv.session_buffer.set_inlay_hints_pending_refresh()
        for sv in not_visible_session_views:
            sv.session_buffer.set_inlay_hints_pending_refresh()

    def m_workspace_diagnostic_refresh(self, params: None, request_id: Any) -> None:
        """handles the workspace/diagnostic/refresh request"""
        self.send_response(Response(request_id, None))
        visible_session_views, not_visible_session_views = self.session_views_by_visibility()
        for sv in visible_session_views:
            sv.session_buffer.do_document_diagnostic_async(sv.view, sv.view.change_count(), forced_update=True)
        for sv in not_visible_session_views:
            sv.session_buffer.set_document_diagnostic_pending_refresh()

    def m_textDocument_publishDiagnostics(self, params: PublishDiagnosticsParams) -> None:
        """handles the textDocument/publishDiagnostics notification"""
        mgr = self.manager()
        if not mgr:
            return
        uri = params["uri"]
        reason = mgr.should_ignore_diagnostics(uri, self.config)
        if isinstance(reason, str):
            debug("ignoring unsuitable diagnostics for", uri, "reason:", reason)
            return
        diagnostics = params["diagnostics"]
        self.diagnostics.add_diagnostics_async(uri, diagnostics)
        mgr.on_diagnostics_updated()
        if sb := self.get_session_buffer_for_uri_async(uri):
            version = params.get('version', sb.last_synced_version)
            self._publish_diagnostics_to_session_buffer_async(sb, diagnostics, version)

    def m_client_registerCapability(self, params: RegistrationParams, request_id: Any) -> None:
        """handles the client/registerCapability request"""
        registrations = params["registrations"]
        for registration in registrations:
            capability_path, registration_path = method_to_capability(registration["method"])
            if self.config.is_disabled_capability(capability_path):
                continue
            debug(f"{self.config.name}: registering capability:", capability_path)
            options = registration.get("registerOptions")
            if not isinstance(options, dict):
                options = {}
            options = self.config.filter_out_disabled_capabilities(capability_path, options)
            registration_id = registration["id"]
            data = _RegistrationData(registration_id, capability_path, registration_path, options)
            self._registrations[registration_id] = data
            if data.selector:
                # The registration is applicable only to certain buffers, so let's check which buffers apply.
                for sb in self.session_buffers_async():
                    data.check_applicable(sb)
            else:
                # The registration applies globally to all buffers.
                self.capabilities.register(registration_id, capability_path, registration_path, options)
                # We must inform our SessionViews of the new capabilities, in case it's for instance a hoverProvider
                # or a completionProvider for trigger characters.
                for sv in self.session_views_async():
                    inform = functools.partial(sv.on_capability_added_async, registration_id, capability_path, options)
                    # Inform only after the response is sent, otherwise we might start doing requests for capabilities
                    # which are technically not yet done registering.
                    sublime.set_timeout_async(inform)
            if capability_path == "didChangeWatchedFilesProvider":
                capability_options = cast('DidChangeWatchedFilesRegistrationOptions', options)
                self.register_file_system_watchers(registration_id, capability_options['watchers'])
        self.send_response(Response(request_id, None))

    def m_client_unregisterCapability(self, params: UnregistrationParams, request_id: Any) -> None:
        """handles the client/unregisterCapability request"""
        unregistrations = params["unregisterations"]  # typo in the official specification
        for unregistration in unregistrations:
            registration_id = unregistration["id"]
            capability_path, registration_path = method_to_capability(unregistration["method"])
            debug(f"{self.config.name}: unregistering capability:", capability_path)
            data = self._registrations.pop(registration_id, None)
            if capability_path == "didChangeWatchedFilesProvider":
                self.unregister_file_system_watchers(registration_id)
            if data and not data.selector:
                discarded = self.capabilities.unregister(registration_id, capability_path, registration_path)
                # We must inform our SessionViews of the removed capabilities, in case it's for instance a hoverProvider
                # or a completionProvider for trigger characters.
                if isinstance(discarded, dict):
                    for sv in self.session_views_async():
                        sv.on_capability_removed_async(registration_id, discarded)
        self.send_response(Response(request_id, None))

    def register_file_system_watchers(self, registration_id: str, watchers: list[FileSystemWatcher]) -> None:
        if not self._watcher_impl:
            return
        self.unregister_file_system_watchers(registration_id)
        # List of patterns aggregated by base path and kind.
        aggregated_watchers: dict[tuple[str, WatchKind], list[str]] = {}
        for config in watchers:
            kind = config.get("kind") or DEFAULT_WATCH_KIND
            glob_pattern = config["globPattern"]
            if isinstance(glob_pattern, str):
                for folder in self.get_workspace_folders():
                    aggregated_watchers.setdefault((folder.path, kind), []).append(glob_pattern)
            else:  # RelativePattern
                pattern = glob_pattern["pattern"]
                base = glob_pattern["baseUri"]  # URI or WorkspaceFolder
                _, base_path = parse_uri(base if isinstance(base, str) else base["uri"])
                aggregated_watchers.setdefault((base_path, kind), []).append(pattern)
        file_watchers: list[FileWatcher] = []
        for (base_path, kind), patterns in aggregated_watchers.items():
            ignores = self._get_global_ignore_globs(base_path)
            watcher_kind = lsp_watch_kind_to_file_watcher_event_types(kind)
            file_watchers.append(self._watcher_impl.create(base_path, patterns, watcher_kind, ignores, self))
        self._dynamic_file_watchers[registration_id] = file_watchers

    def unregister_file_system_watchers(self, registration_id: str) -> None:
        if file_watchers := self._dynamic_file_watchers.pop(registration_id, None):
            for file_watcher in file_watchers:
                file_watcher.destroy()

    def m_window_showDocument(self, params: ShowDocumentParams, request_id: Any) -> None:
        """handles the window/showDocument request"""
        uri = params.get("uri")

        def success(b: None | bool | sublime.View) -> None:
            if isinstance(b, bool):
                pass
            elif isinstance(b, sublime.View):
                b = b.is_valid()
            else:
                b = False
            self.send_response(Response(request_id, {"success": b}))

        if params.get("external"):
            success(open_externally(uri, bool(params.get("takeFocus"))))
        else:
            # TODO: ST API does not allow us to say "do not focus this new view"
            self.open_uri_async(uri, params.get("selection")).then(success)

    def m_window_workDoneProgress_create(self, params: WorkDoneProgressCreateParams, request_id: Any) -> None:
        """handles the window/workDoneProgress/create request"""
        self._progress[params['token']] = None
        self.send_response(Response(request_id, None))

    def _invoke_views(self, request: Request, method: str, *args: Any) -> None:
        if request.view:
            if sv := self.session_view_for_view_async(request.view):
                getattr(sv, method)(*args)
        else:
            for sv in self.session_views_async():
                getattr(sv, method)(*args)

    def _create_window_progress_reporter(self, token: ProgressToken, value: WorkDoneProgressBegin) -> None:
        self._progress[token] = WindowProgressReporter(
            window=self.window,
            key=f"lspprogress{self.config.name}{token}",
            title=value["title"],
            message=value.get("message")
        )

    def m___progress(self, params: ProgressParams) -> None:
        """handles the $/progress notification"""
        token = params['token']
        value = params['value']
        # Partial Result Progress
        # https://microsoft.github.io/language-server-protocol/specifications/specification-current/#partialResults
        if isinstance(token, str) and token.startswith(_PARTIAL_RESULT_PROGRESS_PREFIX):
            request_id = int(token[len(_PARTIAL_RESULT_PROGRESS_PREFIX):])
            request = self._response_handlers[request_id][0]
            if request.method == "workspace/diagnostic":
                self._on_workspace_diagnostics_async(
                    cast(WorkspaceDiagnosticReport, value), reset_pending_response=False)
            return
        # Work Done Progress
        # https://microsoft.github.io/language-server-protocol/specifications/specification-current/#workDoneProgress
        if isinstance(value, dict) and 'kind' in value:
            kind = value['kind']
            if token not in self._progress:
                # If the token is not in the _progress map then that could mean two things:
                #
                # 1) The server is reporting on our client-initiated request progress. In that case, the progress token
                #    should be of the form $_WORK_DONE_PROGRESS_PREFIX$RequestId. We try to parse it, and if it
                #    succeeds, we can delegate to the appropriate session view instances.
                #
                # 2) The server is not spec-compliant and reports progress using server-initiated progress but didn't
                #    call window/workDoneProgress/create before hand. In that case, we check the 'kind' field of the
                #    progress data. If the 'kind' field is 'begin', we set up a progress reporter anyway.
                try:
                    request_id = int(token[len(_WORK_DONE_PROGRESS_PREFIX):])  # type: ignore
                    request = self._response_handlers[request_id][0]
                    self._invoke_views(request, "on_request_progress", request_id, params)
                    return
                except (TypeError, IndexError, ValueError, KeyError):
                    # The parse failed so possibility (1) is apparently not applicable. At this point we may still be
                    # dealing with possibility (2).
                    if kind == 'begin':
                        # We are dealing with possibility (2), so create the progress reporter now.
                        value = cast(WorkDoneProgressBegin, value)
                        self._create_window_progress_reporter(token, value)
                        return
                debug(f'unknown $/progress token: {token}')
                return
            if kind == 'begin':
                value = cast(WorkDoneProgressBegin, value)
                self._create_window_progress_reporter(token, value)
            elif kind == 'report':
                value = cast(WorkDoneProgressReport, value)
                progress = self._progress[token]
                assert isinstance(progress, WindowProgressReporter)
                progress(value.get("message"), value.get("percentage"))
            elif kind == 'end':
                value = cast(WorkDoneProgressEnd, value)
                progress = self._progress.pop(token)
                assert isinstance(progress, WindowProgressReporter)
                title = progress.title
                progress = None
                message = value.get('message')
                if message:
                    self.window.status_message(title + ': ' + message)

    # --- shutdown dance -----------------------------------------------------------------------------------------------

    def end_async(self) -> None:
        # TODO: Ensure this function is called only from the async thread
        if self.exiting:
            return
        self.exiting = True
        if self._plugin:
            self._plugin.on_session_end_async(None, None)
            self._plugin = None
        for sv in self.session_views_async():
            self.shutdown_session_view_async(sv)
        self.capabilities.clear()
        self._registrations.clear()
        for watcher in self._static_file_watchers:
            watcher.destroy()
        self._static_file_watchers = []
        for watcher in itertools.chain.from_iterable(self._dynamic_file_watchers.values()):
            watcher.destroy()
        self._dynamic_file_watchers = {}
        self.state = ClientStates.STOPPING
        self.send_request_async(Request.shutdown(), self._handle_shutdown_result, self._handle_shutdown_result)

    def shutdown_session_view_async(self, session_view: SessionViewProtocol) -> None:
        for status_key in self._status_messages.keys():
            session_view.view.erase_status(status_key)
        session_view.shutdown_async()

    def _handle_shutdown_result(self, _: Any) -> None:
        self.exit()

    def on_transport_close(self, exit_code: int, exception: Exception | None) -> None:
        self.exiting = True
        self.state = ClientStates.STOPPING
        self.transport = None
        self._response_handlers.clear()
        if self._plugin:
            self._plugin.on_session_end_async(exit_code, exception)
            self._plugin = None
        if self._initialize_error:
            # Override potential exit error with a saved one.
            exit_code, exception = self._initialize_error
        if mgr := self.manager():
            if self._init_callback:
                self._init_callback(self, True)
                self._init_callback = None
            mgr.on_post_exit_async(self, exit_code, exception)

    # --- RPC message handling ----------------------------------------------------------------------------------------

    def send_request_async(
            self,
            request: Request,
            on_result: Callable[[Any], None],
            on_error: Callable[[Any], None] | None = None
    ) -> int:
        """You must call this method from Sublime's worker thread. Callbacks will run in Sublime's worker thread."""
        self.request_id += 1
        request_id = self.request_id
        if request.progress and isinstance(request.params, dict):
            request.params["workDoneToken"] = _WORK_DONE_PROGRESS_PREFIX + str(request_id)
        if request.partial_results and isinstance(request.params, dict):
            request.params["partialResultToken"] = _PARTIAL_RESULT_PROGRESS_PREFIX + str(request_id)
        on_error = on_error or (lambda _: None)
        self._response_handlers[request_id] = (request, on_result, on_error)
        self._invoke_views(request, "on_request_started_async", request_id, request)
        if self._plugin:
            self._plugin.on_pre_send_request_async(request_id, request)
        self._logger.outgoing_request(request_id, request.method, request.params)
        self.send_payload(request.to_payload(request_id))
        return request_id

    def send_request(
            self,
            request: Request,
            on_result: Callable[[Any], None],
            on_error: Callable[[Any], None] | None = None,
    ) -> None:
        """You can call this method from any thread. Callbacks will run in Sublime's worker thread."""
        sublime.set_timeout_async(functools.partial(self.send_request_async, request, on_result, on_error))

    def send_request_task(self, request: Request) -> Promise:
        task: PackagedTask[Any] = Promise.packaged_task()
        promise, resolver = task
        self.send_request_async(request, resolver, lambda x: resolver(Error.from_lsp(x)))
        return promise

    def send_request_task_2(self, request: Request) -> tuple[Promise, int]:
        task: PackagedTask[Any] = Promise.packaged_task()
        promise, resolver = task
        request_id = self.send_request_async(request, resolver, lambda x: resolver(Error.from_lsp(x)))
        return (promise, request_id)

    def cancel_request_async(self, request_id: int) -> None:
        if request_id in self._response_handlers:
            self.send_notification(Notification("$/cancelRequest", {"id": request_id}))
            request, _, error_handler = self._response_handlers[request_id]
            error_handler({"code": LSPErrorCodes.RequestCancelled, "message": "Request canceled by client"})
            self._invoke_views(request, "on_request_canceled_async", request_id)
            self._response_handlers[request_id] = (request, lambda *args: None, lambda *args: None)

    def send_notification(self, notification: Notification) -> None:
        if self._plugin:
            self._plugin.on_pre_send_notification_async(notification)
        self._logger.outgoing_notification(notification.method, notification.params)
        self.send_payload(notification.to_payload())

    def send_response(self, response: Response) -> None:
        self._logger.outgoing_response(response.request_id, response.result)
        self.send_payload(response.to_payload())

    def send_error_response(self, request_id: Any, error: Error) -> None:
        self._logger.outgoing_error_response(request_id, error)
        self.send_payload({'jsonrpc': '2.0', 'id': request_id, 'error': error.to_lsp()})

    def exit(self) -> None:
        self.send_notification(Notification.exit())
        try:
            self.transport.close()  # type: ignore
        except AttributeError:
            pass

    def send_payload(self, payload: dict[str, Any]) -> None:
        try:
            self.transport.send(payload)  # type: ignore
        except AttributeError:
            pass

    def deduce_payload(
        self,
        payload: dict[str, Any]
    ) -> tuple[Callable | None, Any, int | None, str | None, str | None]:
        if "method" in payload:
            method = payload["method"]
            handler = self._get_handler(method)
            result = payload.get("params")
            if "id" in payload:
                req_id = payload["id"]
                self._logger.incoming_request(req_id, method, result)
                if handler is None:
                    self.send_error_response(req_id, Error(ErrorCodes.MethodNotFound, method))
                else:
                    return (handler, result, req_id, "request", method)
            else:
                res = (handler, result, None, "notification", method)
                self._logger.incoming_notification(method, result, res[0] is None)
                if self._plugin:
                    self._plugin.on_server_notification_async(Notification(method, result))
                return res
        elif "id" in payload:
            if payload["id"] is None:
                self._logger.incoming_response(None, payload.get("error"), True)
                return (None, None, None, None, None)
            response_id = int(payload["id"])
            handler, method, result, is_error = self.response_handler(response_id, payload)
            self._logger.incoming_response(response_id, result, is_error)
            response = Response(response_id, result)
            if self._plugin and not is_error:
                self._plugin.on_server_response_async(method, response)  # type: ignore
            return handler, response.result, None, None, None
        else:
            debug("Unknown payload type: ", payload)
        return (None, None, None, None, None)

    def on_payload(self, payload: dict[str, Any]) -> None:
        handler, result, req_id, typestr, _method = self.deduce_payload(payload)
        if handler:
            try:
                if req_id is None:
                    # notification or response
                    handler(result)
                else:
                    # request
                    try:
                        handler(result, req_id)
                    except Error as err:
                        self.send_error_response(req_id, err)
                    except Exception as ex:
                        self.send_error_response(req_id, Error.from_exception(ex))
                        raise
            except Exception as err:
                exception_log(f"Error handling {typestr}", err)

    def response_handler(self, response_id: int, response: dict[str, Any]) -> tuple[Callable, str | None, Any, bool]:
        matching_handler = self._response_handlers.pop(response_id)
        if not matching_handler:
            error = {"code": ErrorCodes.InvalidParams, "message": f"unknown response ID {response_id}"}
            return (print_to_status_bar, None, error, True)
        request, handler, error_handler = matching_handler
        self._invoke_views(request, "on_request_finished_async", response_id)
        if "result" in response and "error" not in response:
            return (handler, request.method, response["result"], False)
        if "result" not in response and "error" in response:
            error = response["error"]
        else:
            error = {"code": ErrorCodes.InvalidParams, "message": "invalid response payload"}
        return (error_handler, request.method, error, True)

    def _get_handler(self, method: str) -> Callable | None:
        return getattr(self, method2attr(method), None)
