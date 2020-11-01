import importlib
import importlib.abc
import os
import sublime
import sublime_plugin
import sys
import weakref
import contextlib

_toposorted_modules = []


class _MetaPathFinder(importlib.abc.MetaPathFinder):

    def __init__(self, backend) -> None:
        self.toposort = []
        self._backend = backend

    def find_module(self, fullname, path):
        if fullname.startswith("LSP."):
            _toposorted_modules.append(fullname)
        return self._backend.find_module(fullname, path)

    def invalidate_caches(self) -> None:
        return self._backend.invalidate_caches()


try:
    sys.meta_path.insert(0, _MetaPathFinder(sys.meta_path[0]))

    # Please keep this list sorted (Edit -> Sort Lines)
    from .plugin.code_actions import LspCodeActionsCommand
    from .plugin.completion import LspCompleteInsertTextCommand
    from .plugin.completion import LspCompleteTextEditCommand
    from .plugin.completion import LspResolveDocsCommand
    from .plugin.configuration import LspDisableLanguageServerGloballyCommand
    from .plugin.configuration import LspDisableLanguageServerInProjectCommand
    from .plugin.configuration import LspEnableLanguageServerGloballyCommand
    from .plugin.configuration import LspEnableLanguageServerInProjectCommand
    from .plugin.core.collections import DottedDict
    from .plugin.core.css import load as load_css
    from .plugin.core.handlers import LanguageHandler
    from .plugin.core.logging import exception_log
    from .plugin.core.panels import destroy_output_panels
    from .plugin.core.panels import LspClearPanelCommand
    from .plugin.core.panels import LspUpdatePanelCommand
    from .plugin.core.panels import LspUpdateServerPanelCommand
    from .plugin.core.promise import opening_files
    from .plugin.core.protocol import Response
    from .plugin.core.protocol import WorkspaceFolder
    from .plugin.core.registry import LspRecheckSessionsCommand
    from .plugin.core.registry import LspRestartClientCommand
    from .plugin.core.registry import windows
    from .plugin.core.sessions import AbstractPlugin
    from .plugin.core.sessions import method2attr
    from .plugin.core.sessions import register_plugin
    from .plugin.core.sessions import Session
    from .plugin.core.settings import client_configs
    from .plugin.core.settings import load_settings
    from .plugin.core.settings import unload_settings
    from .plugin.core.transports import kill_all_subprocesses
    from .plugin.core.types import ClientConfig
    from .plugin.core.typing import Optional, List, Type, Callable, Dict, Tuple
    from .plugin.core.views import LspRunTextCommandHelperCommand
    from .plugin.diagnostics import LspHideDiagnosticCommand
    from .plugin.diagnostics import LspNextDiagnosticCommand
    from .plugin.diagnostics import LspPreviousDiagnosticCommand
    from .plugin.documents import DocumentSyncListener
    from .plugin.documents import TextChangeListener
    from .plugin.edit import LspApplyDocumentEditCommand
    from .plugin.execute_command import LspExecuteCommand
    from .plugin.formatting import LspFormatDocumentCommand
    from .plugin.formatting import LspFormatDocumentRangeCommand
    from .plugin.goto import LspSymbolDeclarationCommand
    from .plugin.goto import LspSymbolDefinitionCommand
    from .plugin.goto import LspSymbolImplementationCommand
    from .plugin.goto import LspSymbolTypeDefinitionCommand
    from .plugin.hover import LspHoverCommand
    from .plugin.panels import LspShowDiagnosticsPanelCommand
    from .plugin.panels import LspToggleServerPanelCommand
    from .plugin.references import LspSymbolReferencesCommand
    from .plugin.rename import LspSymbolRenameCommand
    from .plugin.save_command import LspSaveCommand
    from .plugin.selection_range import LspExpandSelectionCommand
    from .plugin.symbols import LspDocumentSymbolsCommand
    from .plugin.symbols import LspSelectionAddCommand
    from .plugin.symbols import LspSelectionClearCommand
    from .plugin.symbols import LspSelectionSetCommand
    from .plugin.symbols import LspWorkspaceSymbolsCommand
    from .plugin.tooling import LspCopyToClipboardFromBase64Command
    from .plugin.tooling import LspDumpBufferCapabilities
    from .plugin.tooling import LspDumpWindowConfigs
    from .plugin.tooling import LspParseVscodePackageJson
    from .plugin.tooling import LspTroubleshootServerCommand

finally:
    sys.meta_path.pop(0)


def _get_final_subclasses(derived: List[Type], results: List[Type]) -> None:
    """
    This function should be removed: https://github.com/sublimelsp/LSP/issues/899
    """
    for d in derived:
        d_subclasses = d.__subclasses__()
        if len(d_subclasses) > 0:
            _get_final_subclasses(d_subclasses, results)
        else:
            results.append(d)


def _register_all_plugins() -> None:
    plugin_classes = []  # type: List[Type[AbstractPlugin]]
    _get_final_subclasses(AbstractPlugin.__subclasses__(), plugin_classes)
    for plugin_class in plugin_classes:
        register_plugin(plugin_class, notify_listener=False)
    language_handler_classes = []  # type: List[Type[LanguageHandler]]
    _get_final_subclasses(LanguageHandler.__subclasses__(), language_handler_classes)
    for language_handler_class in language_handler_classes:
        # Create an ephemeral plugin that stores an instance of the LanguageHandler as a class instance. Custom requests
        # and notifications will work.
        class LanguageHandlerTransition(AbstractPlugin):

            handler = language_handler_class()

            @classmethod
            def name(cls) -> str:
                return cls.handler.name  # type: ignore

            @classmethod
            def configuration(cls) -> Tuple[sublime.Settings, str]:
                file_base_name = cls.name()
                if file_base_name.startswith("lsp-"):
                    file_base_name = "LSP-" + file_base_name[len("lsp-"):]
                settings = sublime.load_settings("{}.sublime-settings".format(file_base_name))
                cfg = cls.handler.config  # type: ignore
                settings.set("command", cfg.command)
                settings.set("settings", cfg.settings.get(None))
                if isinstance(cfg.init_options, DottedDict):
                    init_options = cfg.init_options.get()
                elif isinstance(cfg.init_options, dict):
                    init_options = cfg.init_options
                settings.set("initializationOptions", init_options)
                langs = []  # type: List[Dict[str, str]]
                for language in cfg.languages:
                    langs.append({
                        "languageId": language.id,
                        "document_selector": language.document_selector,
                        "feature_selector": language.feature_selector
                    })
                settings.set("languages", langs)
                return settings, "Packages/{0}/{0}.sublime-settings".format(file_base_name)

            @classmethod
            def can_start(cls, window: sublime.Window, initiating_view: sublime.View,
                          workspace_folders: List[WorkspaceFolder], configuration: ClientConfig) -> Optional[str]:
                if hasattr(cls.handler, 'on_start'):
                    if not cls.handler.on_start(window):  # type: ignore
                        return "{} cannot start".format(cls.name())
                return None

            def __init__(self, weaksession: 'weakref.ref[Session]') -> None:
                super().__init__(weaksession)
                if hasattr(self.handler, 'on_initialized'):
                    self.handler.on_initialized(self)  # type: ignore

            def on_notification(self, method: str, handler: Callable) -> None:
                setattr(self, method2attr(method), handler)

            def on_request(self, method: str, handler: Callable) -> None:
                setattr(self, method2attr(method), handler)

            def send_response(self, response: Response) -> None:
                session = self.weaksession()
                if session:
                    session.send_response(response)

        register_plugin(LanguageHandlerTransition, notify_listener=False)


def _unregister_all_plugins() -> None:
    from LSP.plugin.core.sessions import _plugins
    _plugins.clear()
    client_configs.external.clear()
    client_configs.all.clear()


def plugin_loaded() -> None:
    load_settings()
    load_css()
    _register_all_plugins()
    client_configs.update_configs()
    for window in sublime.windows():
        windows.lookup(window)


def plugin_unloaded() -> None:
    _unregister_all_plugins()
    for window in sublime.windows():
        destroy_output_panels(window)  # references and diagnostics panels
        try:
            windows.lookup(window).plugin_unloaded()
            windows.discard(window)
        except Exception as ex:
            exception_log("failed to unload window", ex)
    unload_settings()
    for module_name in reversed(_toposorted_modules):
        sys.modules.pop(module_name)


class Listener(sublime_plugin.EventListener):

    def on_exit(self) -> None:
        kill_all_subprocesses()

    def on_load_project_async(self, w: sublime.Window) -> None:
        windows.lookup(w).on_load_project_async()

    def on_post_save_project_async(self, w: sublime.Window) -> None:
        windows.lookup(w).on_post_save_project_async()

    def on_new_window_async(self, w: sublime.Window) -> None:
        sublime.set_timeout(lambda: windows.lookup(w))

    def on_pre_close_window(self, w: sublime.Window) -> None:
        windows.discard(w)

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
