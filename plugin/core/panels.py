from re import sub
from .typing import Dict, Optional, List, Generator, Tuple
from .types import debounced
from contextlib import contextmanager
import sublime
import sublime_plugin

PANEL_FILE_REGEX = r"^(?!\s+\d+:\d+)(.*)(:)$"
PANEL_LINE_REGEX = r"^\s+(\d+):(\d+)"

# about 80 chars per line implies maintaining a buffer of about 40kb per window
SERVER_PANEL_MAX_LINES = 500

# If nothing else shows up after 80ms, actually print the messages to the panel
SERVER_PANEL_DEBOUNCE_TIME_MS = 80

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


class Panel:
    def __init__(self, name: str, syntax="", file_regex="", line_regex=""):
        self.name = name
        self._panel = None  # type: Optional[sublime.View]
        self._syntax = syntax
        self._file_regex = file_regex
        self._line_regex = line_regex

    def view(self, w: sublime.Window) -> sublime.View:
        """ Returns the view contained within the panel. """
        return self._ensure_panel(w)

    def is_open(self, w: sublime.Window) -> bool:
        return w.active_panel() == "output.{}".format(self.name)

    def open(self, w: sublime.Window) -> None:
        self._panel = self._ensure_panel(w)
        w.run_command("show_panel", {"panel": "output.{}".format(self.name)})

        # HACK: Focus the panel to make the next_result prev_result commands work,
        # than focus back to the currently open view
        current_view = w.active_view()
        w.focus_view(self._panel)
        w.focus_view(current_view)

    def close(self, w: sublime.Window) -> None:
        self._panel = self._ensure_panel(w)
        w.run_command("hide_panel", {"panel": "output.{}".format(self.name)})

    def toggle(self, w: sublime.Window) -> None:
        if self.is_open(w):
            self.close(w)
        else:
            self.open(w)

    def update(self, w: sublime.Window, content: str) -> None:
        self._panel = self._ensure_panel(w)
        self._panel.run_command("lsp_update_panel", {"characters": content})

    def clear(self, w: sublime.Window) -> None:
        self._panel = self._ensure_panel(w)
        self._panel.run_command("lsp_clear_panel")

    def destroy(self, w: sublime.Window) -> None:
        self._panel = self._ensure_panel(w)
        self._panel.settings().set("syntax", "Packages/Text/Plain text.tmLanguage")
        w.destroy_output_panel(self.name)

    def _ensure_panel(self, w: sublime.Window) -> sublime.View:
        panel = w.find_output_panel(self.name);
        if panel:
            return panel
        panel = create_output_panel(w, self.name)

        if self._file_regex:
            panel.settings().set("result_file_regex", self._file_regex)
        if self._line_regex:
            panel.settings().set("result_line_regex", self._line_regex)
        if self._syntax:
            panel.assign_syntax(self._syntax)

        # All our panels are read-only
        panel.set_read_only(True)
        return panel


diagnostics_panel = Panel(
    "diagnostics",
    syntax="Packages/LSP/Syntaxes/Diagnostics.sublime-syntax",
    file_regex=PANEL_FILE_REGEX,
    line_regex=PANEL_LINE_REGEX
)

reference_panel = Panel(
    "references",
    syntax="Packages/LSP/Syntaxes/References.sublime-syntax",
    file_regex=PANEL_FILE_REGEX,
    line_regex=PANEL_LINE_REGEX
)

language_servers_panel = Panel(
    "language servers",
    syntax="Packages/LSP/Syntaxes/ServerLog.sublime-syntax",
)

rename_panel = Panel(
    "rename",
    syntax="Packages/LSP/Syntaxes/References.sublime-syntax",
    file_regex=PANEL_FILE_REGEX,
    line_regex=PANEL_LINE_REGEX
)

lsp_panels = [diagnostics_panel, reference_panel, language_servers_panel, rename_panel]


@contextmanager
def mutable(view: sublime.View) -> Generator:
    view.set_read_only(False)
    yield
    view.set_read_only(True)


def create_output_panel(window: sublime.Window, name: str) -> sublime.View:
    panel = window.create_output_panel(name)
    settings = panel.settings()
    for key, value in OUTPUT_PANEL_SETTINGS.items():
        settings.set(key, value)
    return panel


def destroy_output_panels(window: sublime.Window) -> None:
    for panel in lsp_panels:
        panel.destroy(window)


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

    def run(self, edit: sublime.Edit, characters: Optional[str] = "") -> None:
        # Clear folds
        self.view.unfold(sublime.Region(0, self.view.size()))

        with mutable(self.view):
            self.view.replace(edit, sublime.Region(0, self.view.size()), characters or "")

        # Clear the selection
        selection = self.view.sel()
        selection.clear()


def update_server_panel(window: sublime.Window, prefix: str, message: str) -> None:
    if not window.is_valid():
        return
    window_id = window.id()
    panel_view = language_servers_panel.view(window)
    if not panel_view.is_valid():
        return
    LspUpdateServerPanelCommand.to_be_processed.setdefault(window_id, []).append((prefix, message))
    previous_length = len(LspUpdateServerPanelCommand.to_be_processed[window_id])

    def condition() -> bool:
        if not panel_view:
            return False
        if not panel_view.is_valid():
            return False
        to_process = LspUpdateServerPanelCommand.to_be_processed.get(window_id)
        if to_process is None:
            return False
        current_length = len(to_process)
        if current_length >= 10:
            # Do not let the queue grow large.
            return True
        # If the queue remains stable, flush the messages.
        return current_length == previous_length

    debounced(
        lambda: panel_view.run_command("lsp_update_server_panel", {"window_id": window_id}) if panel_view else None,
        SERVER_PANEL_DEBOUNCE_TIME_MS,
        condition
    )


class LspUpdateServerPanelCommand(sublime_plugin.TextCommand):

    to_be_processed = {}  # type: Dict[int, List[Tuple[str, str]]]

    def run(self, edit: sublime.Edit, window_id: int) -> None:
        to_process = self.to_be_processed.pop(window_id)
        with mutable(self.view):
            for prefix, message in to_process:
                message = message.replace("\r\n", "\n")  # normalize Windows eol
                self.view.insert(edit, self.view.size(), "{}: {}\n".format(prefix, message))
                total_lines, _ = self.view.rowcol(self.view.size())
                point = 0  # Starting from point 0 in the panel ...
                regions = []  # type: List[sublime.Region]
            for _ in range(0, max(0, total_lines - SERVER_PANEL_MAX_LINES)):
                # ... collect all regions that span an entire line ...
                region = self.view.full_line(point)
                regions.append(region)
                point = region.b
            for region in reversed(regions):
                # ... and erase them in reverse order
                self.view.erase(edit, region)
