import sublime
import sublime_plugin

from ..color import remove_color_boxes
from ..diagnostics import DiagnosticsPresenter
from ..highlights import remove_highlights
from .handlers import LanguageHandler
from .logging import set_debug_logging, set_exception_logging
from .panels import destroy_output_panels, ensure_panel, PanelName
from .popups import popups
from .protocol import Response
from .protocol import WorkspaceFolder
from .registry import windows, unload_sessions
from .rpc import method2attr
from .sessions import AbstractPlugin
from .sessions import register_plugin
from .sessions import Session
from .settings import client_configs
from .settings import settings, load_settings, unload_settings
from .transports import kill_all_subprocesses
from .types import ClientConfig
from .typing import Optional, List, Type, Callable, Dict
import weakref


def ensure_server_panel(window: sublime.Window) -> Optional[sublime.View]:
    return ensure_panel(window, PanelName.LanguageServers, "", "", "Packages/LSP/Syntaxes/ServerLog.sublime-syntax")


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


def _forcefully_register_plugins() -> None:
    """
    This function should be removed: https://github.com/sublimelsp/LSP/issues/899
    """
    plugin_classes = []  # type: List[Type[AbstractPlugin]]
    _get_final_subclasses(AbstractPlugin.__subclasses__(), plugin_classes)
    for plugin_class in plugin_classes:
        register_plugin(plugin_class)
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
            def configuration(cls) -> sublime.Settings:
                file_base_name = cls.name()
                if file_base_name.startswith("lsp-"):
                    file_base_name = "LSP-" + file_base_name[len("lsp-"):]
                settings = sublime.load_settings("{}.sublime-settings".format(file_base_name))
                cfg = cls.handler.config  # type: ignore
                settings.set("command", cfg.binary_args)
                settings.set("settings", cfg.settings.get(None))
                settings.set("initializationOptions", cfg.init_options)
                langs = []  # type: List[Dict[str, str]]
                for language in cfg.languages:
                    langs.append({
                        "languageId": language.id,
                        "document_selector": language.document_selector,
                        "feature_selector": language.feature_selector
                    })
                settings.set("languages", langs)
                return settings

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

        register_plugin(LanguageHandlerTransition)


def startup() -> None:
    load_settings()
    popups.load_css()
    set_debug_logging(settings.log_debug)
    set_exception_logging(True)
    _forcefully_register_plugins()  # Remove this function: https://github.com/sublimelsp/LSP/issues/899
    client_configs.update_configs()
    windows.set_diagnostics_ui(DiagnosticsPresenter)
    windows.set_server_panel_factory(ensure_server_panel)
    windows.set_settings_factory(settings)
    sublime.status_message("LSP initialized")
    window = sublime.active_window()
    if window:
        windows.lookup(window).start_active_views()


def shutdown() -> None:
    # Also needs to handle package being disabled or removed
    # https://github.com/sublimelsp/LSP/issues/375
    unload_settings()
    # TODO: Move to __del__ methods
    for window in sublime.windows():
        unload_sessions(window)  # unloads view state from document sync and diagnostics
        destroy_output_panels(window)  # references and diagnostics panels
        for view in window.views():
            if view.file_name():
                remove_highlights(view)
                remove_color_boxes(view)
                for key in ['error', 'warning', 'info', 'hint', 'diagnostics']:
                    view.erase_regions('lsp_{}'.format(key))
                for key in ['diagnostics', 'clients']:
                    view.erase_status('lsp_{}'.format(key))
                for key in ['language', 'active', 'diagnostic_phantom']:
                    view.settings().erase('lsp_{}'.format(key))


class Listener(sublime_plugin.EventListener):
    def on_exit(self) -> None:
        kill_all_subprocesses()

    def on_load_project(self, w: sublime.Window) -> None:
        windows.lookup(w).on_load_project()

    def on_pre_close_project(self, w: sublime.Window) -> None:
        windows.lookup(w).on_pre_close_project()
