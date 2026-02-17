from __future__ import annotations

# Please keep this list sorted (Edit -> Sort Lines)
from .plugin.code_actions import LspCodeActionsCommand, LspRefactorCommand, LspSourceActionCommand
from .plugin.code_lens import LspCodeLensCommand, LspToggleCodeLensesCommand
from .plugin.color import LspColorPresentationCommand
from .plugin.completion import (
    LspCommitCompletionWithOppositeInsertMode,
    LspResolveDocsCommand,
    LspSelectCompletionCommand,
)
from .plugin.configuration import (
    LspDisableLanguageServerGloballyCommand,
    LspDisableLanguageServerInProjectCommand,
    LspEnableLanguageServerGloballyCommand,
    LspEnableLanguageServerInProjectCommand,
)
from .plugin.core.constants import ST_VERSION
from .plugin.core.css import load as load_css
from .plugin.core.open import opening_files
from .plugin.core.panels import PanelName
from .plugin.core.registry import (
    LspCheckApplicableCommand,
    LspNextDiagnosticCommand,
    LspOpenLocationCommand,
    LspPrevDiagnosticCommand,
    LspRestartServerCommand,
    windows,
)
from .plugin.core.sessions import AbstractPlugin, register_plugin
from .plugin.core.settings import client_configs, load_settings, unload_settings
from .plugin.core.signature_help import LspSignatureHelpNavigateCommand, LspSignatureHelpShowCommand
from .plugin.core.transports import kill_all_subprocesses
from .plugin.core.tree_view import LspCollapseTreeItemCommand, LspExpandTreeItemCommand
from .plugin.core.views import LspRunTextCommandHelperCommand
from .plugin.document_link import LspOpenLinkCommand
from .plugin.documents import DocumentSyncListener, TextChangeListener
from .plugin.edit import LspApplyDocumentEditCommand, LspApplyWorkspaceEditCommand, LspConcludeWorkspaceEditPanelCommand
from .plugin.execute_command import LspExecuteCommand
from .plugin.folding_range import LspFoldAllCommand, LspFoldCommand
from .plugin.formatting import LspFormatCommand, LspFormatDocumentCommand, LspFormatDocumentRangeCommand
from .plugin.goto import (
    LspGotoDiagnosticCommand,
    LspSymbolDeclarationCommand,
    LspSymbolDefinitionCommand,
    LspSymbolImplementationCommand,
    LspSymbolTypeDefinitionCommand,
)
from .plugin.hierarchy import LspCallHierarchyCommand, LspHierarchyToggleCommand, LspTypeHierarchyCommand
from .plugin.hover import LspCopyTextCommand, LspHoverCommand, LspToggleHoverPopupsCommand
from .plugin.inlay_hint import LspInlayHintClickCommand, LspToggleInlayHintsCommand
from .plugin.panels import (
    LspClearLogPanelCommand,
    LspClearPanelCommand,
    LspShowDiagnosticsPanelCommand,
    LspToggleLogPanelLinesLimitCommand,
    LspToggleServerPanelCommand,
    LspUpdateLogPanelCommand,
    LspUpdatePanelCommand,
)
from .plugin.references import LspSymbolReferencesCommand
from .plugin.rename import LspSymbolRenameCommand
from .plugin.rename_file import LspRenamePathCommand
from .plugin.save_command import LspSaveAllCommand, LspSaveCommand
from .plugin.selection_range import LspExpandSelectionCommand
from .plugin.semantic_highlighting import LspShowScopeNameCommand
from .plugin.symbols import (
    LspDocumentSymbolsCommand,
    LspSelectionAddCommand,
    LspSelectionClearCommand,
    LspSelectionSetCommand,
    LspWorkspaceSymbolsCommand,
)
from .plugin.tooling import (
    LspCopyToClipboardFromBase64Command,
    LspDumpBufferCapabilities,
    LspDumpWindowConfigs,
    LspOnDoubleClickCommand,
    LspParseVscodePackageJson,
    LspTroubleshootServerCommand,
)
from typing import Any
import os
import sublime
import sublime_plugin

__all__ = (
    "DocumentSyncListener",
    "Listener",
    "LspApplyDocumentEditCommand",
    "LspApplyWorkspaceEditCommand",
    "LspCallHierarchyCommand",
    "LspCheckApplicableCommand",
    "LspClearLogPanelCommand",
    "LspClearPanelCommand",
    "LspCodeActionsCommand",
    "LspCodeLensCommand",
    "LspCollapseTreeItemCommand",
    "LspColorPresentationCommand",
    "LspCommitCompletionWithOppositeInsertMode",
    "LspConcludeWorkspaceEditPanelCommand",
    "LspCopyTextCommand",
    "LspCopyToClipboardFromBase64Command",
    "LspDisableLanguageServerGloballyCommand",
    "LspDisableLanguageServerInProjectCommand",
    "LspDocumentSymbolsCommand",
    "LspDumpBufferCapabilities",
    "LspDumpWindowConfigs",
    "LspEnableLanguageServerGloballyCommand",
    "LspEnableLanguageServerInProjectCommand",
    "LspExecuteCommand",
    "LspExpandSelectionCommand",
    "LspExpandTreeItemCommand",
    "LspFoldAllCommand",
    "LspFoldCommand",
    "LspFormatCommand",
    "LspFormatDocumentCommand",
    "LspFormatDocumentRangeCommand",
    "LspGotoDiagnosticCommand",
    "LspHierarchyToggleCommand",
    "LspHoverCommand",
    "LspInlayHintClickCommand",
    "LspNextDiagnosticCommand",
    "LspOnDoubleClickCommand",
    "LspOpenLinkCommand",
    "LspOpenLocationCommand",
    "LspParseVscodePackageJson",
    "LspPrevDiagnosticCommand",
    "LspRefactorCommand",
    "LspRenamePathCommand",
    "LspResolveDocsCommand",
    "LspRestartServerCommand",
    "LspRunTextCommandHelperCommand",
    "LspSaveAllCommand",
    "LspSaveCommand",
    "LspSelectCompletionCommand",
    "LspSelectionAddCommand",
    "LspSelectionClearCommand",
    "LspSelectionSetCommand",
    "LspShowDiagnosticsPanelCommand",
    "LspShowScopeNameCommand",
    "LspSignatureHelpNavigateCommand",
    "LspSignatureHelpShowCommand",
    "LspSourceActionCommand",
    "LspSymbolDeclarationCommand",
    "LspSymbolDefinitionCommand",
    "LspSymbolImplementationCommand",
    "LspSymbolReferencesCommand",
    "LspSymbolRenameCommand",
    "LspSymbolTypeDefinitionCommand",
    "LspToggleCodeLensesCommand",
    "LspToggleHoverPopupsCommand",
    "LspToggleInlayHintsCommand",
    "LspToggleLogPanelLinesLimitCommand",
    "LspToggleServerPanelCommand",
    "LspTroubleshootServerCommand",
    "LspTypeHierarchyCommand",
    "LspUpdateLogPanelCommand",
    "LspUpdatePanelCommand",
    "LspWorkspaceSymbolsCommand",
    "TextChangeListener",
    "plugin_loaded",
    "plugin_unloaded",
)


def _get_final_subclasses(derived: list[type], results: list[type]) -> None:
    for d in derived:
        d_subclasses = d.__subclasses__()
        if len(d_subclasses) > 0:
            _get_final_subclasses(d_subclasses, results)
        else:
            results.append(d)


def _register_all_plugins() -> None:
    plugin_classes: list[type[AbstractPlugin]] = []
    _get_final_subclasses(AbstractPlugin.__subclasses__(), plugin_classes)
    for plugin_class in plugin_classes:
        try:
            if not plugin_class.name():
                continue
        except NotImplementedError:
            continue
        register_plugin(plugin_class, notify_listener=False)


def _unregister_all_plugins() -> None:
    from LSP.plugin.core.sessions import _plugins

    _plugins.clear()
    client_configs.external.clear()
    client_configs.all.clear()


def plugin_loaded() -> None:
    load_settings()
    load_css()
    windows.enable()
    _register_all_plugins()
    client_configs.update_configs()
    # TODO: remove this in the next minor release
    base_scope_map = sublime.load_settings("language-ids.sublime-settings")
    if base_scope_map.to_dict():
        def show_warning():
            print("LSP - The language-ids.sublime-settings file is deprecated, but it looks like you have it.\nSee the migration guide -> https://github.com/sublimelsp/LSP/issues/2592")  # noqa: E501
            sublime.status_message("LSP - The language-ids.sublime-settings file is deprecated. Open the Console for details.")  # noqa: E501

        sublime.set_timeout(show_warning, 5_000)


def plugin_unloaded() -> None:
    _unregister_all_plugins()
    windows.disable()
    unload_settings()


class Listener(sublime_plugin.EventListener):

    def on_exit(self) -> None:
        kill_all_subprocesses()

    def on_load_project_async(self, window: sublime.Window) -> None:
        if manager := windows.lookup(window):
            manager.on_load_project_async()

    def on_post_save_project_async(self, window: sublime.Window) -> None:
        if manager := windows.lookup(window):
            manager.on_post_save_project_async()

    def on_new_window_async(self, window: sublime.Window) -> None:
        sublime.set_timeout(lambda: windows.lookup(window))

    def on_pre_close_window(self, window: sublime.Window) -> None:
        windows.discard(window)

    def on_pre_move(self, view: sublime.View) -> None:
        if ST_VERSION < 4184:  # https://github.com/sublimehq/sublime_text/issues/4630#issuecomment-2502781628
            # Workaround for ViewEventListener.on_post_move_async not being triggered when air-dropping a tab:
            # https://github.com/sublimehq/sublime_text/issues/4630
            listeners = sublime_plugin.view_event_listeners.get(view.id())
            if not isinstance(listeners, list):
                return
            for listener in listeners:
                if isinstance(listener, DocumentSyncListener):
                    # we need a small delay here, so that the DocumentSyncListener will recognize a possible new window
                    sublime.set_timeout_async(listener.on_post_move_window_async, 1)
                    return

    def on_load(self, view: sublime.View) -> None:
        file_name = view.file_name()
        if not file_name:
            return
        for fn in opening_files.keys():
            if fn == file_name or os.path.samefile(fn, file_name):
                # Remove it from the pending opening files, and resolve the promise.
                opening_files.pop(fn)[1](view)
                break

    def on_pre_close(self, view: sublime.View) -> None:
        file_name = view.file_name()
        if not file_name:
            return
        for fn in opening_files:
            if fn == file_name or os.path.samefile(fn, file_name):
                tup = opening_files.pop(fn, None)
                if tup:
                    # The view got closed before it finished loading. This can happen.
                    tup[1](None)
                    break

    def on_window_command(
        self, window: sublime.Window, command_name: str, args: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        if command_name == "rename_path":
            return ('lsp_rename_path', args)
        return None

    def on_post_window_command(self, window: sublime.Window, command_name: str, args: dict[str, Any] | None) -> None:
        if command_name == "show_panel":
            wm = windows.lookup(window)
            if not wm:
                return
            panel_manager = wm.panel_manager
            if not panel_manager:
                return
            if panel_manager.is_panel_open(PanelName.Diagnostics):
                sublime.set_timeout_async(wm.update_diagnostics_panel_async)
            elif panel_manager.is_panel_open(PanelName.Log):
                sublime.set_timeout(lambda: panel_manager.update_log_panel(scroll_to_selection=True))
