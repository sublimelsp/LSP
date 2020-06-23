import sublime

from ..color import remove_color_boxes
from ..diagnostics import DiagnosticsPresenter
from ..highlights import remove_highlights
from .logging import set_debug_logging, set_exception_logging
from .panels import destroy_output_panels, ensure_panel, PanelName
from .popups import popups
from .registry import windows, load_handlers, unload_sessions
from .settings import settings, load_settings, unload_settings
from .typing import Optional


def ensure_server_panel(window: sublime.Window) -> Optional[sublime.View]:
    return ensure_panel(window, PanelName.LanguageServers, "", "", "Packages/LSP/Syntaxes/ServerLog.sublime-syntax")


def plugin_loaded() -> None:
    load_settings()
    popups.load_css()
    set_debug_logging(settings.log_debug)
    set_exception_logging(True)
    windows.set_diagnostics_ui(DiagnosticsPresenter)
    windows.set_server_panel_factory(ensure_server_panel)
    windows.set_settings_factory(settings)
    load_handlers()
    sublime.status_message("LSP initialized")
    window = sublime.active_window()
    if window:
        windows.lookup(window).start_active_views()
    if int(sublime.version()) > 4000:
        sublime.error_message(
            """The currently installed version of LSP package is not compatible with Sublime Text 4. """
            """Please remove and reinstall this package to receive a version compatible with ST4. """
            """Remember to restart Sublime Text after.""")


def plugin_unloaded() -> None:
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
