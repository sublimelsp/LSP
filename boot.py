from __future__ import annotations
import os
import sublime
import sublime_plugin

# Please keep this list sorted (Edit -> Sort Lines)
from .plugin.code_actions import LspCodeActionsCommand  # noqa: F401
from .plugin.code_actions import LspRefactorCommand  # noqa: F401
from .plugin.code_actions import LspSourceActionCommand  # noqa: F401
from .plugin.code_lens import LspCodeLensCommand  # noqa: F401
from .plugin.code_lens import LspToggleCodeLensesCommand  # noqa: F401
from .plugin.color import LspColorPresentationCommand  # noqa: F401
from .plugin.completion import LspCommitCompletionWithOppositeInsertMode  # noqa: F401
from .plugin.completion import LspResolveDocsCommand  # noqa: F401
from .plugin.completion import LspSelectCompletionCommand  # noqa: F401
from .plugin.configuration import LspDisableLanguageServerGloballyCommand  # noqa: F401
from .plugin.configuration import LspDisableLanguageServerInProjectCommand  # noqa: F401
from .plugin.configuration import LspEnableLanguageServerGloballyCommand  # noqa: F401
from .plugin.configuration import LspEnableLanguageServerInProjectCommand  # noqa: F401
from .plugin.core.collections import DottedDict  # noqa: F401
from .plugin.core.css import load as load_css
from .plugin.core.open import opening_files
from .plugin.core.panels import PanelName
from .plugin.core.protocol import Error  # noqa: F401
from .plugin.core.registry import LspNextDiagnosticCommand  # noqa: F401
from .plugin.core.registry import LspOpenLocationCommand  # noqa: F401
from .plugin.core.registry import LspPrevDiagnosticCommand  # noqa: F401
from .plugin.core.registry import LspRestartServerCommand  # noqa: F401
from .plugin.core.registry import windows
from .plugin.core.sessions import AbstractPlugin
from .plugin.core.sessions import register_plugin
from .plugin.core.settings import client_configs
from .plugin.core.settings import load_settings
from .plugin.core.settings import unload_settings
from .plugin.core.signature_help import LspSignatureHelpNavigateCommand  # noqa: F401
from .plugin.core.signature_help import LspSignatureHelpShowCommand  # noqa: F401
from .plugin.core.transports import kill_all_subprocesses
from .plugin.core.tree_view import LspCollapseTreeItemCommand  # noqa: F401
from .plugin.core.tree_view import LspExpandTreeItemCommand  # noqa: F401
from .plugin.core.views import LspRunTextCommandHelperCommand  # noqa: F401
from .plugin.document_link import LspOpenLinkCommand  # noqa: F401
from .plugin.documents import DocumentSyncListener  # noqa: F401
from .plugin.documents import TextChangeListener  # noqa: F401
from .plugin.edit import LspApplyDocumentEditCommand  # noqa: F401
from .plugin.edit import LspApplyWorkspaceEditCommand  # noqa: F401
from .plugin.execute_command import LspExecuteCommand  # noqa: F401
from .plugin.folding_range import LspFoldAllCommand  # noqa: F401
from .plugin.folding_range import LspFoldCommand  # noqa: F401
from .plugin.formatting import LspFormatCommand  # noqa: F401
from .plugin.formatting import LspFormatDocumentCommand  # noqa: F401
from .plugin.formatting import LspFormatDocumentRangeCommand  # noqa: F401
from .plugin.goto import LspSymbolDeclarationCommand  # noqa: F401
from .plugin.goto import LspSymbolDefinitionCommand  # noqa: F401
from .plugin.goto import LspSymbolImplementationCommand  # noqa: F401
from .plugin.goto import LspSymbolTypeDefinitionCommand  # noqa: F401
from .plugin.goto_diagnostic import LspGotoDiagnosticCommand  # noqa: F401
from .plugin.hierarchy import LspCallHierarchyCommand  # noqa: F401
from .plugin.hierarchy import LspHierarchyToggleCommand  # noqa: F401
from .plugin.hierarchy import LspTypeHierarchyCommand  # noqa: F401
from .plugin.hover import LspHoverCommand  # noqa: F401
from .plugin.hover import LspToggleHoverPopupsCommand  # noqa: F401
from .plugin.inlay_hint import LspInlayHintClickCommand  # noqa: F401
from .plugin.inlay_hint import LspToggleInlayHintsCommand  # noqa: F401
from .plugin.panels import LspClearLogPanelCommand  # noqa: F401
from .plugin.panels import LspClearPanelCommand  # noqa: F401
from .plugin.panels import LspShowDiagnosticsPanelCommand  # noqa: F401
from .plugin.panels import LspToggleLogPanelLinesLimitCommand  # noqa: F401
from .plugin.panels import LspToggleServerPanelCommand  # noqa: F401
from .plugin.panels import LspUpdateLogPanelCommand  # noqa: F401
from .plugin.panels import LspUpdatePanelCommand  # noqa: F401
from .plugin.references import LspSymbolReferencesCommand  # noqa: F401
from .plugin.rename import LspHideRenameButtonsCommand  # noqa: F401
from .plugin.rename import LspSymbolRenameCommand  # noqa: F401
from .plugin.save_command import LspSaveAllCommand  # noqa: F401
from .plugin.save_command import LspSaveCommand  # noqa: F401
from .plugin.selection_range import LspExpandSelectionCommand  # noqa: F401
from .plugin.semantic_highlighting import LspShowScopeNameCommand  # noqa: F401
from .plugin.symbols import LspDocumentSymbolsCommand  # noqa: F401
from .plugin.symbols import LspSelectionAddCommand  # noqa: F401
from .plugin.symbols import LspSelectionClearCommand  # noqa: F401
from .plugin.symbols import LspSelectionSetCommand  # noqa: F401
from .plugin.symbols import LspWorkspaceSymbolsCommand  # noqa: F401
from .plugin.tooling import LspCopyToClipboardFromBase64Command  # noqa: F401
from .plugin.tooling import LspDumpBufferCapabilities  # noqa: F401
from .plugin.tooling import LspDumpWindowConfigs  # noqa: F401
from .plugin.tooling import LspOnDoubleClickCommand  # noqa: F401
from .plugin.tooling import LspParseVscodePackageJson  # noqa: F401
from .plugin.tooling import LspTroubleshootServerCommand  # noqa: F401
from typing import Any


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


def plugin_unloaded() -> None:
    _unregister_all_plugins()
    windows.disable()
    unload_settings()


class Listener(sublime_plugin.EventListener):
    def on_exit(self) -> None:
        kill_all_subprocesses()

    def on_load_project_async(self, w: sublime.Window) -> None:
        manager = windows.lookup(w)
        if manager:
            manager.on_load_project_async()

    def on_post_save_project_async(self, w: sublime.Window) -> None:
        manager = windows.lookup(w)
        if manager:
            manager.on_post_save_project_async()

    def on_new_window_async(self, w: sublime.Window) -> None:
        sublime.set_timeout(lambda: windows.lookup(w))

    def on_pre_close_window(self, w: sublime.Window) -> None:
        windows.discard(w)

    # Note: EventListener.on_post_move_async does not fire when a tab is moved out of the current window in such a way
    # that a new window is created: https://github.com/sublimehq/sublime_text/issues/4630
    # Hence, as a workaround we use on_pre_move, which still works in that case.
    def on_pre_move(self, view: sublime.View) -> None:
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
        for fn in opening_files.keys():
            if fn == file_name or os.path.samefile(fn, file_name):
                tup = opening_files.pop(fn, None)
                if tup:
                    # The view got closed before it finished loading. This can happen.
                    tup[1](None)
                    break

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
