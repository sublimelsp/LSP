import sublime
from .plugin import __version__

if __version__ <= (0, 11, 0) and int(sublime.version()) > 4000:
    sublime.error_message(
        """Installed version of LSP package is not compatible with Sublime Text 4.\n"""
        """Please remove and re-install this package to receive ST4-compatible version."""
    )


# Please keep this list sorted (Edit -> Sort Lines)
from .plugin.code_actions import LspCodeActionBulbListener
from .plugin.code_actions import LspCodeActionsCommand
from .plugin.color import LspColorListener
from .plugin.completion import CompletionHandler
from .plugin.completion import CompletionHelper
from .plugin.completion import LspTrimCompletionCommand
from .plugin.configuration import LspDisableLanguageServerGloballyCommand
from .plugin.configuration import LspDisableLanguageServerInProjectCommand
from .plugin.configuration import LspEnableLanguageServerGloballyCommand
from .plugin.configuration import LspEnableLanguageServerInProjectCommand
from .plugin.core.documents import DocumentSyncListener
from .plugin.core.main import shutdown as plugin_unloaded
from .plugin.core.main import startup as plugin_loaded
from .plugin.core.panels import LspClearPanelCommand
from .plugin.core.panels import LspUpdatePanelCommand
from .plugin.core.panels import LspUpdateServerPanelCommand
from .plugin.core.registry import LspRestartClientCommand
from .plugin.diagnostics import DiagnosticsCursorListener
from .plugin.diagnostics import LspClearDiagnosticsCommand
from .plugin.diagnostics import LspHideDiagnosticCommand
from .plugin.diagnostics import LspNextDiagnosticCommand
from .plugin.diagnostics import LspPreviousDiagnosticCommand
from .plugin.edit import LspApplyDocumentEditCommand
from .plugin.edit import LspApplyWorkspaceEditCommand
from .plugin.execute_command import LspExecuteCommand
from .plugin.formatting import FormatOnSaveListener
from .plugin.formatting import LspFormatDocumentCommand
from .plugin.formatting import LspFormatDocumentRangeCommand
from .plugin.goto import LspSymbolDeclarationCommand
from .plugin.goto import LspSymbolDefinitionCommand
from .plugin.goto import LspSymbolImplementationCommand
from .plugin.goto import LspSymbolTypeDefinitionCommand
from .plugin.highlights import DocumentHighlightListener
from .plugin.hover import HoverHandler
from .plugin.hover import LspHoverCommand
from .plugin.panels import LspShowDiagnosticsPanelCommand
from .plugin.panels import LspToggleServerPanelCommand
from .plugin.references import LspSymbolReferencesCommand
from .plugin.rename import LspSymbolRenameCommand
from .plugin.signature_help import SignatureHelpListener
from .plugin.symbols import LspDocumentSymbolsCommand
from .plugin.symbols import LspSelectionAddCommand
from .plugin.symbols import LspSelectionClearCommand
from .plugin.symbols import LspWorkspaceSymbolsCommand
