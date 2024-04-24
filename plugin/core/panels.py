from __future__ import annotations
from .types import PANEL_FILE_REGEX
from .types import PANEL_LINE_REGEX
from typing import Iterable, Optional
import sublime


LOG_LINES_LIMIT_SETTING_NAME = 'lsp_limit_lines'
MAX_LOG_LINES_LIMIT_ON = 500
MAX_LOG_LINES_LIMIT_OFF = 10000
OUTPUT_PANEL_SETTINGS = {
    "auto_indent": False,
    "draw_indent_guides": False,
    "draw_unicode_white_space": "none",
    "draw_white_space": "none",
    "fold_buttons": True,
    "gutter": True,
    "is_widget": True,
    "line_numbers": False,
    "lsp_active": True,
    "margin": 3,
    "match_brackets": False,
    "rulers": [],
    "scroll_past_end": False,
    "show_definitions": False,
    "tab_size": 4,
    "translate_tabs_to_spaces": False,
    "word_wrap": False
}


class PanelName:
    Diagnostics = "diagnostics"
    References = "references"
    Rename = "rename"
    Log = "LSP Log Panel"


class PanelManager:
    def __init__(self, window: sublime.Window) -> None:
        self._window = window
        self._rename_panel_buttons: Optional[sublime.PhantomSet] = None

    def destroy_output_panels(self) -> None:
        for field in filter(lambda a: not a.startswith('__'), PanelName.__dict__.keys()):
            panel_name = getattr(PanelName, field)
            panel = self._window.find_output_panel(panel_name)
            if panel and panel.is_valid():
                panel.settings().set("syntax", "Packages/Text/Plain text.tmLanguage")
                self._window.destroy_output_panel(panel_name)
        self._rename_panel_buttons = None

    def toggle_output_panel(self, panel_type: str) -> None:
        panel_name = "output.{}".format(panel_type)
        command = "hide_panel" if self.is_panel_open(panel_type) else "show_panel"
        self._window.run_command(command, {"panel": panel_name})

    def is_panel_open(self, panel_name: str) -> bool:
        return self._window.is_valid() and self._window.active_panel() == "output.{}".format(panel_name)

    def update_log_panel(self, scroll_to_selection: bool = False) -> None:
        panel = self.ensure_log_panel()
        if panel and self.is_panel_open(PanelName.Log):
            panel.run_command("lsp_update_log_panel")
            if scroll_to_selection:
                panel.show(panel.sel(), animate=False)

    def ensure_panel(self, name: str, result_file_regex: str, result_line_regex: str,
                     syntax: str, context_menu: Optional[str] = None) -> Optional[sublime.View]:
        return self.get_panel(name) or \
            self._create_panel(name, result_file_regex, result_line_regex, syntax, context_menu)

    def ensure_diagnostics_panel(self) -> Optional[sublime.View]:
        return self.ensure_panel("diagnostics", PANEL_FILE_REGEX, PANEL_LINE_REGEX,
                                 "Packages/LSP/Syntaxes/Diagnostics.sublime-syntax")

    def ensure_log_panel(self) -> Optional[sublime.View]:
        return self.ensure_panel(PanelName.Log, "", "", "Packages/LSP/Syntaxes/ServerLog.sublime-syntax",
                                 "Context LSP Log Panel.sublime-menu")

    def ensure_references_panel(self) -> Optional[sublime.View]:
        return self.ensure_panel("references", PANEL_FILE_REGEX, PANEL_LINE_REGEX,
                                 "Packages/LSP/Syntaxes/References.sublime-syntax")

    def ensure_rename_panel(self) -> Optional[sublime.View]:
        return self.ensure_panel(PanelName.Rename, PANEL_FILE_REGEX, PANEL_LINE_REGEX,
                                 "Packages/LSP/Syntaxes/References.sublime-syntax")

    def get_panel(self, panel_name: str) -> Optional[sublime.View]:
        return self._window.find_output_panel(panel_name)

    def _create_panel(self, name: str, result_file_regex: str, result_line_regex: str,
                      syntax: str, context_menu: Optional[str] = None) -> Optional[sublime.View]:
        panel = self.create_output_panel(name)
        if not panel:
            return None
        if name == PanelName.Rename:
            self._rename_panel_buttons = sublime.PhantomSet(panel, "lsp_rename_buttons")
        settings = panel.settings()
        if result_file_regex:
            settings.set("result_file_regex", result_file_regex)
        if result_line_regex:
            settings.set("result_line_regex", result_line_regex)
        if context_menu:
            settings.set("context_menu", context_menu)
        panel.assign_syntax(syntax)
        # Call create_output_panel a second time after assigning the above settings, so that it'll be picked up
        # as a result buffer. See: Packages/Default/exec.py#L228-L230
        panel = self._window.create_output_panel(name)
        if panel:
            # All our panels are read-only
            panel.set_read_only(True)
        return panel

    def create_output_panel(self, name: str) -> Optional[sublime.View]:
        panel = self._window.create_output_panel(name)
        settings = panel.settings()
        for key, value in OUTPUT_PANEL_SETTINGS.items():
            settings.set(key, value)
        return panel

    def show_diagnostics_panel_async(self) -> None:
        if self._window.active_panel() is None:
            self.toggle_output_panel(PanelName.Diagnostics)

    def hide_diagnostics_panel_async(self) -> None:
        if self.is_panel_open(PanelName.Diagnostics):
            self.toggle_output_panel(PanelName.Diagnostics)

    def update_rename_panel_buttons(self, phantoms: Iterable[sublime.Phantom]) -> None:
        if self._rename_panel_buttons:
            self._rename_panel_buttons.update(phantoms)
