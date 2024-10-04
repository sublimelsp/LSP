from __future__ import annotations
from .collections import DottedDict
from .constants import SEMANTIC_TOKENS_MAP
from .diagnostics_storage import DiagnosticsStorage
from .edit import apply_text_edits
from .edit import parse_workspace_edit
from .edit import WorkspaceChanges
from .file_watcher import DEFAULT_KIND
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
from .protocol import ClientCapabilities
from .protocol import CodeAction, CodeActionKind
from .protocol import CodeLensExtended
from .protocol import Command
from .protocol import CompletionItemKind
from .protocol import CompletionItemTag
from .protocol import Diagnostic
from .protocol import DiagnosticServerCancellationData
from .protocol import DiagnosticSeverity
from .protocol import DiagnosticTag
from .protocol import DidChangeWatchedFilesRegistrationOptions
from .protocol import DidChangeWorkspaceFoldersParams
from .protocol import DocumentDiagnosticReportKind
from .protocol import DocumentLink
from .protocol import DocumentUri
from .protocol import Error
from .protocol import ErrorCodes
from .protocol import ExecuteCommandParams
from .protocol import FailureHandlingKind
from .protocol import FileEvent
from .protocol import FoldingRangeKind
from .protocol import GeneralClientCapabilities
from .protocol import InitializeError
from .protocol import InitializeParams
from .protocol import InitializeResult
from .protocol import InsertTextMode
from .protocol import Location
from .protocol import LocationLink
from .protocol import LogMessageParams
from .protocol import LSPAny
from .protocol import LSPErrorCodes
from .protocol import LSPObject
from .protocol import MarkupKind
from .protocol import Notification
from .protocol import PrepareSupportDefaultBehavior
from .protocol import PreviousResultId
from .protocol import ProgressParams
from .protocol import ProgressToken
from .protocol import PublishDiagnosticsParams
from .protocol import RegistrationParams
from .protocol import Range
from .protocol import Request
from .protocol import Response
from .protocol import ResponseError
from .protocol import SemanticTokenModifiers
from .protocol import SemanticTokenTypes
from .protocol import SymbolKind
from .protocol import SymbolTag
from .protocol import TextDocumentClientCapabilities
from .protocol import TextDocumentSyncKind
from .protocol import TextEdit
from .protocol import TokenFormat
from .protocol import UnregistrationParams
from .protocol import WindowClientCapabilities
from .protocol import WorkDoneProgressBegin
from .protocol import WorkDoneProgressCreateParams
from .protocol import WorkDoneProgressEnd
from .protocol import WorkDoneProgressReport
from .protocol import WorkspaceClientCapabilities
from .protocol import WorkspaceDiagnosticParams
from .protocol import WorkspaceDiagnosticReport
from .protocol import WorkspaceDocumentDiagnosticReport
from .protocol import WorkspaceFullDocumentDiagnosticReport
from .protocol import WorkspaceEdit
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
from .types import SettingsRegistration
from .types import sublime_pattern_to_glob
from .types import WORKSPACE_DIAGNOSTICS_TIMEOUT
from .typing import StrEnum
from .url import filename_to_uri
from .url import parse_uri
from .url import unparse_uri
from .version import __version__
from .views import extract_variables
from .views import get_storage_path
from .views import get_uri_and_range_from_location
from .views import MarkdownLangMap
from .workspace import is_subpath_of
from .workspace import WorkspaceFolder
from abc import ABCMeta
from abc import abstractmethod
from abc import abstractproperty
from enum import IntEnum, IntFlag
from typing import Any, Callable, Generator, List, Protocol, TypeVar
from typing import cast
from typing_extensions import TypeAlias, TypeGuard
from weakref import WeakSet
import functools
import mdpopups
import os
import sublime
import weakref

InitCallback: TypeAlias = Callable[['Session', bool], None]
T = TypeVar('T')


class ViewStateActions(IntFlag):
    Close = 2
    Save = 1


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
    token_modifiers = [modifiers_legend[idx]
                       for idx, val in enumerate(reversed(bin(token_modifiers_encoded)[2:])) if val == "1"]
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

    @abstractproperty
    def window(self) -> sublime.Window:
        """
        Get the window associated with this manager.
        """
        raise NotImplementedError()

    @abstractmethod
    def sessions(self, view: sublime.View, capability: str | None = None) -> Generator[Session, None, None]:
        """
        Iterate over the sessions stored in this manager, applicable to the given view, with the given capability.
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
            # https://python-markdown.github.io
            "parser": "Python-Markdown",
            "version": mdpopups.markdown.__version__  # type: ignore
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
        workspace_capabilites["didChangeWatchedFiles"] = {"dynamicRegistration": True}
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

    def get_resolved_code_lenses_for_region(self, region: sublime.Region) -> Generator[CodeLensExtended, None, None]:
        ...

    def start_code_lenses_async(self) -> None:
        ...

    def clear_code_lenses_async(self) -> None:
        ...

    def set_code_lenses_pending_refresh(self, needs_refresh: bool = True) -> None:
        ...

    def reset_show_definitions(self) -> None:
        ...

    def on_userprefs_changed_async(self) -> None:
        ...


class SessionBufferProtocol(Protocol):

    @property
    def session(self) -> Session:
        ...

    @property
    def session_views(self) -> WeakSet[SessionViewProtocol]:
        ...

    @property
    def version(self) -> int | None:
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
        options: dict[str, Any]
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
        self, raw_diagnostics: list[Diagnostic], version: int | None, visible_session_views: set[SessionViewProtocol]
    ) -> None:
        ...

    def get_document_link_at_point(self, view: sublime.View, point: int) -> DocumentLink | None:
        ...

    def update_document_link(self, new_link: DocumentLink) -> None:
        ...

    def do_semantic_tokens_async(self, view: sublime.View) -> None:
        ...

    def set_semantic_tokens_pending_refresh(self, needs_refresh: bool = True) -> None:
        ...

    def get_semantic_tokens(self) -> list[Any]:
        ...

    def do_inlay_hints_async(self, view: sublime.View) -> None:
        ...

    def set_inlay_hints_pending_refresh(self, needs_refresh: bool = True) -> None:
        ...

    def remove_inlay_hint_phantom(self, phantom_uuid: str) -> None:
        ...

    def do_document_diagnostic_async(self, view: sublime.View, version: int | None = None) -> None:
        ...

    def set_document_diagnostic_pending_refresh(self, needs_refresh: bool = True) -> None:
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
    def on_session_initialized_async(self, session: Session) -> None:
        raise NotImplementedError()

    @abstractmethod
    def on_session_shutdown_async(self, session: Session) -> None:
        raise NotImplementedError()

    @abstractmethod
    def diagnostics_intersecting_region_async(
        self,
        region: sublime.Region
    ) -> tuple[list[tuple[SessionBufferProtocol, list[Diagnostic]]], sublime.Region]:
        raise NotImplementedError()

    @abstractmethod
    def diagnostics_touching_point_async(
        self,
        pt: int,
        max_diagnostic_severity_level: int = DiagnosticSeverity.Hint
    ) -> tuple[list[tuple[SessionBufferProtocol, list[Diagnostic]]], sublime.Region]:
        raise NotImplementedError()

    def diagnostics_intersecting_async(
        self,
        region_or_point: sublime.Region | int
    ) -> tuple[list[tuple[SessionBufferProtocol, list[Diagnostic]]], sublime.Region]:
        if isinstance(region_or_point, int):
            return self.diagnostics_touching_point_async(region_or_point)
        elif region_or_point.empty():
            return self.diagnostics_touching_point_async(region_or_point.a)
        else:
            return self.diagnostics_intersecting_region_async(region_or_point)

    @abstractmethod
    def on_diagnostics_updated_async(self, is_view_visible: bool) -> None:
        raise NotImplementedError()

    @abstractmethod
    def on_code_lens_capability_registered_async(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    def get_language_id(self) -> str:
        raise NotImplementedError()

    @abstractmethod
    def get_uri(self) -> DocumentUri:
        raise NotImplementedError()

    @abstractmethod
    def do_signature_help_async(self, manual: bool) -> None:
        raise NotImplementedError()

    @abstractmethod
    def navigate_signature_help(self, forward: bool) -> None:
        raise NotImplementedError()

    @abstractmethod
    def on_post_move_window_async(self) -> None:
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
        return get_storage_path()

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
    def should_ignore(cls, view: sublime.View) -> bool:
        """
        Exclude a view from being handled by the language server, even if it matches the URI scheme(s) and selector from
        the configuration. This can be used to, for example, ignore certain file patterns which are listed in a
        configuration file (e.g. .gitignore). Please note that this also means that no document syncronization
        notifications (textDocument/didOpen, textDocument/didChange, textDocument/didClose, etc.) are sent to the server
        for ignored views, when they are opened in the editor. Therefore this method should be used with caution for
        language servers which index all files in the workspace.
        """
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

    def on_workspace_configuration(self, params: dict, configuration: Any) -> Any:
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

    def on_open_uri_async(self, uri: DocumentUri, callback: Callable[[str, str, str], None]) -> bool:
        """
        Called when a language server reports to open an URI. If you know how to handle this URI, then return True and
        invoke the passed-in callback some time.

        The arguments of the provided callback work as follows:

        - The first argument is the title of the view that will be populated with the content of a new scratch view
        - The second argument is the content of the view
        - The third argument is the syntax to apply for the new view
        """
        return False

    def on_session_buffer_changed_async(self, session_buffer: SessionBufferProtocol) -> None:
        """
        Called when the context of the session buffer has changed or a new buffer was opened.
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

    def check_applicable(self, sb: SessionBufferProtocol) -> None:
        for sv in sb.session_views:
            if self.selector.matches(sv.view):
                self.session_buffers.add(sb)
                sb.register_capability_async(
                    self.registration_id, self.capability_path, self.registration_path, self.options)
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
        self._response_handlers: dict[int, tuple[Request, Callable, Callable[[Any], None] | None]] = {}
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

    def set_window_status_async(self, key: str, message: str) -> None:
        self._status_messages[key] = message
        for sv in self.session_views_async():
            sv.view.set_status(key, message)

    def erase_window_status_async(self, key: str) -> None:
        self._status_messages.pop(key, None)
        for sv in self.session_views_async():
            sv.view.erase_status(key)

    # --- session buffer management ------------------------------------------------------------------------------------

    def register_session_buffer_async(self, sb: SessionBufferProtocol) -> None:
        self._session_buffers.add(sb)
        for data in self._registrations.values():
            data.check_applicable(sb)
        uri = sb.get_uri()
        if uri:
            diagnostics = self.diagnostics.diagnostics_by_document_uri(uri)
            if diagnostics:
                self._publish_diagnostics_to_session_buffer_async(sb, diagnostics, version=None)

    def _publish_diagnostics_to_session_buffer_async(
        self, sb: SessionBufferProtocol, diagnostics: list[Diagnostic], version: int | None
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
        if self._plugin and self._plugin.should_ignore(view):
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
            sv = self.session_view_for_view_async(view)
            if sv:
                return sv.has_capability_async(capability)
            else:
                return self.has_capability(capability)
        return False

    def has_capability(self, capability: str) -> bool:
        value = self.get_capability(capability)
        return value is not False and value is not None

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
        execute_commands = self.get_capability('executeCommandProvider.commands')
        if execute_commands:
            debug(f"{self.config.name}: Supported execute commands: {execute_commands}")
        code_action_kinds = self.get_capability('codeActionProvider.codeActionKinds')
        if code_action_kinds:
            debug(f'{self.config.name}: supported code action kinds: {code_action_kinds}')
        semantic_token_types = cast(List[str], self.get_capability('semanticTokensProvider.legend.tokenTypes'))
        if semantic_token_types:
            debug(f'{self.config.name}: Supported semantic token types: {semantic_token_types}')
        semantic_token_modifiers = cast(List[str], self.get_capability('semanticTokensProvider.legend.tokenModifiers'))
        if semantic_token_modifiers:
            debug(f'{self.config.name}: Supported semantic token modifiers: {semantic_token_modifiers}')
        if self._watcher_impl:
            config = self.config.file_watcher
            patterns = config.get('patterns')
            if patterns:
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
        mgr = self.manager()
        if mgr:
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
            extra_vars = self._plugin_class.additional_variables()
            if extra_vars:
                variables.update(extra_vars)
        return variables

    def execute_command(
        self, command: ExecuteCommandParams, progress: bool, view: sublime.View | None = None
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
                listener.do_signature_help_async(manual=False)

            sublime.set_timeout_async(run_async)
            return Promise.resolve(None)
        # TODO: Our Promise class should be able to handle errors/exceptions
        return Promise(
            lambda resolve: self.send_request(
                Request("workspace/executeCommand", command, None, progress),
                resolve,
                lambda err: resolve(Error(err["code"], err["message"], err.get("data")))
            )
        )

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
            return self.execute_command(command_params, progress, view)
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
        flags: int = 0,
        group: int = -1
    ) -> Promise[sublime.View | None] | None:
        if uri.startswith("file:"):
            return self._open_file_uri_async(uri, r, flags, group)
        # Try to find a pre-existing session-buffer
        sb = self.get_session_buffer_for_uri_async(uri)
        if sb:
            view = sb.get_view_in_group(group)
            self.window.focus_view(view)
            if r:
                center_selection(view, r)
            return Promise.resolve(view)
        # There is no pre-existing session-buffer, so we have to go through AbstractPlugin.on_open_uri_async.
        if self._plugin:
            return self._open_uri_with_plugin_async(self._plugin, uri, r, flags, group)
        return None

    def open_uri_async(
        self,
        uri: DocumentUri,
        r: Range | None = None,
        flags: int = 0,
        group: int = -1
    ) -> Promise[sublime.View | None]:
        promise = self.try_open_uri_async(uri, r, flags, group)
        return Promise.resolve(None) if promise is None else promise

    def _open_file_uri_async(
        self,
        uri: DocumentUri,
        r: Range | None = None,
        flags: int = 0,
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
        flags: int,
        group: int,
    ) -> Promise[sublime.View | None] | None:
        # I cannot type-hint an unpacked tuple
        pair: PackagedTask[tuple[str, str, str]] = Promise.packaged_task()
        # It'd be nice to have automatic tuple unpacking continuations
        callback = lambda a, b, c: pair[1]((a, b, c))  # noqa: E731
        if plugin.on_open_uri_async(uri, callback):
            result: PackagedTask[sublime.View | None] = Promise.packaged_task()

            def open_scratch_buffer(title: str, content: str, syntax: str) -> None:
                if group > -1:
                    self.window.focus_group(group)
                v = self.window.new_file(syntax=syntax, flags=flags)
                # Note: the __init__ of ViewEventListeners is invoked in the next UI frame, so we can fill in the
                # settings object here at our leisure.
                v.settings().set("lsp_uri", uri)
                v.set_scratch(True)
                v.set_name(title)
                v.run_command("append", {"characters": content})
                v.set_read_only(True)
                if r:
                    center_selection(v, r)
                sublime.set_timeout_async(lambda: result[1](v))

            pair[0].then(lambda tup: sublime.set_timeout(lambda: open_scratch_buffer(*tup)))
            return result[0]
        return None

    def open_location_async(self, location: Location | LocationLink, flags: int = 0,
                            group: int = -1) -> Promise[sublime.View | None]:
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
                session_view = self.session_view_for_view_async(view)
                if session_view:
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
        edit = code_action.get("edit")
        is_refactoring = code_action.get('kind') == CodeActionKind.Refactor
        promise = self.apply_workspace_edit_async(edit, is_refactoring) if edit else Promise.resolve(None)
        command = code_action.get("command")
        if command is not None:
            execute_command: ExecuteCommandParams = {
                "command": command["command"],
            }
            arguments = command.get("arguments")
            if arguments is not None:
                execute_command['arguments'] = arguments
            return promise.then(lambda _: self.execute_command(execute_command, progress=False, view=view))
        return promise

    def apply_workspace_edit_async(self, edit: WorkspaceEdit, is_refactoring: bool = False) -> Promise[None]:
        """
        Apply workspace edits, and return a promise that resolves on the async thread again after the edits have been
        applied.
        """
        return self.apply_parsed_workspace_edits(parse_workspace_edit(edit), is_refactoring)

    def apply_parsed_workspace_edits(self, changes: WorkspaceChanges, is_refactoring: bool = False) -> Promise[None]:
        active_sheet = self.window.active_sheet()
        selected_sheets = self.window.selected_sheets()
        promises: list[Promise[None]] = []
        auto_save = userprefs().refactoring_auto_save if is_refactoring else 'never'
        for uri, (edits, view_version) in changes.items():
            view_state_actions = self._get_view_state_actions(uri, auto_save)
            promises.append(
                self.open_uri_async(uri).then(functools.partial(self._apply_text_edits, edits, view_version, uri))
                    .then(functools.partial(self._set_view_state, view_state_actions))
            )
        return Promise.all(promises) \
            .then(lambda _: self._set_selected_sheets(selected_sheets)) \
            .then(lambda _: self._set_focused_sheet(active_sheet))

    def _apply_text_edits(
        self, edits: list[TextEdit], view_version: int | None, uri: str, view: sublime.View | None
    ) -> sublime.View | None:
        if view is None or not view.is_valid():
            print(f'LSP: ignoring edits due to no view for uri: {uri}')
            return None
        apply_text_edits(view, edits, required_view_version=view_version)
        return view

    def _get_view_state_actions(self, uri: DocumentUri, auto_save: str) -> int:
        """
        Determine the required actions for a view after applying a WorkspaceEdit, depending on the
        "refactoring_auto_save" user setting. Returns a bitwise combination of ViewStateActions.Save and
        ViewStateActions.Close, or 0 if no action is necessary.
        """
        if auto_save == 'never':
            return 0  # Never save or close automatically
        scheme, filepath = parse_uri(uri)
        if scheme != 'file':
            return 0  # Can't save or close unsafed buffers (and other schemes) without user dialog
        view = self.window.find_open_file(filepath)
        if view:
            is_opened = True
            is_dirty = view.is_dirty()
        else:
            is_opened = False
            is_dirty = False
        actions = 0
        if auto_save == 'always':
            actions |= ViewStateActions.Save  # Always save
            if not is_opened:
                actions |= ViewStateActions.Close  # Close if file was previously closed
        elif auto_save == 'preserve':
            if not is_dirty:
                actions |= ViewStateActions.Save  # Only save if file didn't have unsaved changes
            if not is_opened:
                actions |= ViewStateActions.Close  # Close if file was previously closed
        elif auto_save == 'preserve_opened':
            if is_opened and not is_dirty:
                # Only save if file was already open and didn't have unsaved changes, but never close
                actions |= ViewStateActions.Save
        return actions

    def _set_view_state(self, actions: int, view: sublime.View | None) -> None:
        if not view:
            return
        should_save = bool(actions & ViewStateActions.Save)
        should_close = bool(actions & ViewStateActions.Close)
        if should_save and view.is_dirty():
            # The save operation must be blocking in case the tab should be closed afterwards
            view.run_command('save', {'async': not should_close, 'quiet': True})
        if should_close and not view.is_dirty():
            if view != self.window.active_view():
                self.window.focus_view(view)
            self.window.run_command('close')

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
        identifier = self.get_capability("diagnosticProvider.identifier")
        if identifier:
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
                if sb and sb.version != version:
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

    def m_window_showMessageRequest(self, params: Any, request_id: Any) -> None:
        """handles the window/showMessageRequest request"""
        self.call_manager('handle_message_request', self, params, request_id)

    def m_window_showMessage(self, params: Any) -> None:
        """handles the window/showMessage notification"""
        self.call_manager('handle_show_message', self, params)

    def m_window_logMessage(self, params: LogMessageParams) -> None:
        """handles the window/logMessage notification"""
        self.call_manager('handle_log_message', self, params)

    def m_workspace_workspaceFolders(self, _: Any, request_id: Any) -> None:
        """handles the workspace/workspaceFolders request"""
        self.send_response(Response(request_id, [wf.to_lsp() for wf in self._workspace_folders]))

    def m_workspace_configuration(self, params: dict[str, Any], request_id: Any) -> None:
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

    def m_workspace_applyEdit(self, params: Any, request_id: Any) -> None:
        """handles the workspace/applyEdit request"""
        self.apply_workspace_edit_async(params.get('edit', {})) \
            .then(lambda _: self.send_response(Response(request_id, {"applied": True})))

    def m_workspace_codeLens_refresh(self, _: Any, request_id: Any) -> None:
        """handles the workspace/codeLens/refresh request"""
        self.send_response(Response(request_id, None))
        if self.uses_plugin():
            visible_session_views, not_visible_session_views = self.session_views_by_visibility()
            for sv in visible_session_views:
                sv.start_code_lenses_async()
            for sv in not_visible_session_views:
                sv.set_code_lenses_pending_refresh()

    def m_workspace_semanticTokens_refresh(self, params: Any, request_id: Any) -> None:
        """handles the workspace/semanticTokens/refresh request"""
        self.send_response(Response(request_id, None))
        visible_session_views, not_visible_session_views = self.session_views_by_visibility()
        for sv in visible_session_views:
            sv.session_buffer.do_semantic_tokens_async(sv.view)
        for sv in not_visible_session_views:
            sv.session_buffer.set_semantic_tokens_pending_refresh()

    def m_workspace_inlayHint_refresh(self, params: None, request_id: Any) -> None:
        """handles the workspace/inlayHint/refresh request"""
        self.send_response(Response(request_id, None))
        visible_session_views, not_visible_session_views = self.session_views_by_visibility()
        for sv in visible_session_views:
            sv.session_buffer.do_inlay_hints_async(sv.view)
        for sv in not_visible_session_views:
            sv.session_buffer.set_inlay_hints_pending_refresh()

    def m_workspace_diagnostic_refresh(self, params: None, request_id: Any) -> None:
        """handles the workspace/diagnostic/refresh request"""
        self.send_response(Response(request_id, None))
        visible_session_views, not_visible_session_views = self.session_views_by_visibility()
        for sv in visible_session_views:
            sv.session_buffer.do_document_diagnostic_async(sv.view)
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
            return debug("ignoring unsuitable diagnostics for", uri, "reason:", reason)
        diagnostics = params["diagnostics"]
        self.diagnostics.add_diagnostics_async(uri, diagnostics)
        mgr.on_diagnostics_updated()
        sb = self.get_session_buffer_for_uri_async(uri)
        if sb:
            self._publish_diagnostics_to_session_buffer_async(sb, diagnostics, params.get('version'))

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
            if self._watcher_impl and capability_path == "didChangeWatchedFilesProvider":
                capability_options = cast(DidChangeWatchedFilesRegistrationOptions, options)
                file_watchers: list[FileWatcher] = []
                for config in capability_options.get("watchers", []):
                    pattern = config.get("globPattern", '')
                    if not isinstance(pattern, str):
                        print('LSP: Relative glob patterns are not supported in File Watcher yet.')
                        continue
                    kind = lsp_watch_kind_to_file_watcher_event_types(config.get("kind") or DEFAULT_KIND)
                    for folder in self.get_workspace_folders():
                        ignores = self._get_global_ignore_globs(folder.path)
                        watcher = self._watcher_impl.create(folder.path, [pattern], kind, ignores, self)
                        file_watchers.append(watcher)
                self._dynamic_file_watchers[registration_id] = file_watchers
        self.send_response(Response(request_id, None))

    def m_client_unregisterCapability(self, params: UnregistrationParams, request_id: Any) -> None:
        """handles the client/unregisterCapability request"""
        unregistrations = params["unregisterations"]  # typo in the official specification
        for unregistration in unregistrations:
            registration_id = unregistration["id"]
            capability_path, registration_path = method_to_capability(unregistration["method"])
            debug(f"{self.config.name}: unregistering capability:", capability_path)
            data = self._registrations.pop(registration_id, None)
            if self._watcher_impl and capability_path == "workspace.didChangeWatchedFiles":
                file_watchers = self._dynamic_file_watchers.pop(registration_id, None)
                if file_watchers:
                    for file_watcher in file_watchers:
                        file_watcher.destroy()
            if data and not data.selector:
                discarded = self.capabilities.unregister(registration_id, capability_path, registration_path)
                # We must inform our SessionViews of the removed capabilities, in case it's for instance a hoverProvider
                # or a completionProvider for trigger characters.
                if isinstance(discarded, dict):
                    for sv in self.session_views_async():
                        sv.on_capability_removed_async(registration_id, discarded)
        self.send_response(Response(request_id, None))

    def m_window_showDocument(self, params: Any, request_id: Any) -> None:
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
            sv = self.session_view_for_view_async(request.view)
            if sv:
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
            for status_key in self._status_messages.keys():
                sv.view.erase_status(status_key)
            sv.shutdown_async()
        self.capabilities.clear()
        self._registrations.clear()
        for watcher in self._static_file_watchers:
            watcher.destroy()
        self._static_file_watchers = []
        for watchers in self._dynamic_file_watchers.values():
            for watcher in watchers:
                watcher.destroy()
        self._dynamic_file_watchers = {}
        self.state = ClientStates.STOPPING
        self.send_request_async(Request.shutdown(), self._handle_shutdown_result, self._handle_shutdown_result)

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
        mgr = self.manager()
        if mgr:
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

    def cancel_request(self, request_id: int, ignore_response: bool = True) -> None:
        self.send_notification(Notification("$/cancelRequest", {"id": request_id}))
        if ignore_response and request_id in self._response_handlers:
            request, _, _ = self._response_handlers[request_id]
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
                    tup = (handler, result, req_id, "request", method)
                    return tup
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

    def response_handler(
        self,
        response_id: int,
        response: dict[str, Any]
    ) -> tuple[Callable | None, str | None, Any, bool]:
        request, handler, error_handler = self._response_handlers.pop(response_id, (None, None, None))
        if not request:
            error = {"code": ErrorCodes.InvalidParams, "message": f"unknown response ID {response_id}"}
            return (print_to_status_bar, None, error, True)
        self._invoke_views(request, "on_request_finished_async", response_id)
        if "result" in response and "error" not in response:
            return (handler, request.method, response["result"], False)
        if not error_handler:
            error_handler = print_to_status_bar
        if "result" not in response and "error" in response:
            error = response["error"]
        else:
            error = {"code": ErrorCodes.InvalidParams, "message": "invalid response payload"}
        return (error_handler, request.method, error, True)

    def _get_handler(self, method: str) -> Callable | None:
        return getattr(self, method2attr(method), None)
