from __future__ import annotations

from .core.panels import LOG_LINES_LIMIT_SETTING_NAME
from .core.panels import PanelName
from .core.registry import windows
from contextlib import contextmanager
from sublime_plugin import WindowCommand
from typing import Generator
import sublime
import sublime_plugin


@contextmanager
def mutable(view: sublime.View) -> Generator:
    view.set_read_only(False)
    yield
    view.set_read_only(True)


def clear_undo_stack(view: sublime.View) -> None:
    clear_undo_stack = getattr(view, "clear_undo_stack", None)
    if not callable(clear_undo_stack):
        return
    # The clear_undo_stack method cannot be called from within a text command...
    sublime.set_timeout(clear_undo_stack)


class LspToggleServerPanelCommand(WindowCommand):
    def run(self) -> None:
        wm = windows.lookup(self.window)
        if not wm:
            return
        panel_manager = wm.panel_manager
        if not panel_manager:
            return
        panel_manager.ensure_log_panel()
        panel_manager.toggle_output_panel(PanelName.Log)


class LspShowDiagnosticsPanelCommand(WindowCommand):
    def run(self) -> None:
        wm = windows.lookup(self.window)
        if not wm:
            return
        panel_manager = wm.panel_manager
        if not panel_manager:
            return
        panel_manager.ensure_diagnostics_panel()
        panel_manager.toggle_output_panel(PanelName.Diagnostics)


class LspToggleLogPanelLinesLimitCommand(sublime_plugin.TextCommand):
    @classmethod
    def is_limit_enabled(cls, window: sublime.Window | None) -> bool:
        wm = windows.lookup(window)
        return bool(wm and wm.is_log_lines_limit_enabled())

    @classmethod
    def get_lines_limit(cls, window: sublime.Window | None) -> int:
        wm = windows.lookup(window)
        return wm.get_log_lines_limit() if wm else 0

    def is_checked(self) -> bool:
        return self.is_limit_enabled(self.view.window())

    def run(self, edit: sublime.Edit) -> None:
        wm = windows.lookup(self.view.window())
        if not wm:
            return
        if panel := wm.panel_manager and wm.panel_manager.get_panel(PanelName.Log):
            settings = panel.settings()
            settings.set(LOG_LINES_LIMIT_SETTING_NAME, not self.is_limit_enabled(wm.window))


class LspClearPanelCommand(sublime_plugin.TextCommand):
    """
    A clear_panel command to clear the error panel.
    """
    def run(self, edit: sublime.Edit) -> None:
        with mutable(self.view):
            self.view.erase(edit, sublime.Region(0, self.view.size()))


class LspUpdatePanelCommand(sublime_plugin.TextCommand):
    """
    A update_panel command to update the error panel with new text.
    """

    def run(self, edit: sublime.Edit, characters: str | None = "") -> None:
        # Clear folds
        self.view.unfold(sublime.Region(0, self.view.size()))

        with mutable(self.view):
            self.view.replace(edit, sublime.Region(0, self.view.size()), characters or "")

        # Clear the selection
        selection = self.view.sel()
        selection.clear()
        clear_undo_stack(self.view)


class LspUpdateLogPanelCommand(sublime_plugin.TextCommand):

    def run(self, edit: sublime.Edit) -> None:
        wm = windows.lookup(self.view.window())
        if not wm:
            return
        with mutable(self.view):
            new_lines = []
            for prefix, message in wm.get_and_clear_server_log():
                message = message.replace("\r\n", "\n")  # normalize Windows eol
                new_lines.append(f"{prefix}: {message}\n")
            if new_lines:
                self.view.insert(edit, self.view.size(), ''.join(new_lines))
                last_region_end = 0  # Starting from point 0 in the panel ...
                total_lines, _ = self.view.rowcol(self.view.size())
                max_lines = LspToggleLogPanelLinesLimitCommand.get_lines_limit(self.view.window())
                for _ in range(0, max(0, total_lines - max_lines)):
                    # ... collect all regions that span an entire line ...
                    region = self.view.full_line(last_region_end)
                    last_region_end = region.b
                erase_region = sublime.Region(0, last_region_end)
                if not erase_region.empty():
                    self.view.erase(edit, erase_region)
        clear_undo_stack(self.view)


class LspClearLogPanelCommand(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit) -> None:
        wm = windows.lookup(self.view.window())
        if not wm:
            return
        if panel := wm.panel_manager and wm.panel_manager.ensure_log_panel():
            panel.run_command("lsp_clear_panel")
