import sublime
import sublime_plugin
from contextlib import contextmanager

try:
    from typing import Optional, Any, List, Generator
    assert Optional and Any and List and Generator
except ImportError:
    pass


# about 80 chars per line implies maintaining a buffer of about 40kb per window
SERVER_PANEL_MAX_LINES = 500


OUTPUT_PANEL_SETTINGS = {
    "auto_indent": False,
    "draw_indent_guides": False,
    "draw_white_space": "None",
    "gutter": True,
    "is_widget": True,
    "line_numbers": False,
    "margin": 3,
    "match_brackets": False,
    "rulers": [],
    "scroll_past_end": False,
    "tab_size": 4,
    "translate_tabs_to_spaces": False,
    "word_wrap": False,
    "fold_buttons": True
}


@contextmanager
def mutable(view: sublime.View) -> 'Generator':
    view.set_read_only(False)
    yield
    view.set_read_only(True)


def create_output_panel(window: sublime.Window, name: str) -> 'Optional[sublime.View]':
    panel = window.create_output_panel(name)
    settings = panel.settings()
    for key, value in OUTPUT_PANEL_SETTINGS.items():
        settings.set(key, value)
    return panel


def destroy_output_panels(window: sublime.Window) -> None:
    for panel_name in ["references", "diagnostics", "server"]:
        window.destroy_output_panel(panel_name)


def create_panel(window: sublime.Window, name: str, result_file_regex: str, result_line_regex: str,
                 syntax: str) -> 'Optional[sublime.View]':
    panel = create_output_panel(window, name)
    if not panel:
        return None
    panel.settings().set("result_file_regex", result_file_regex)
    panel.settings().set("result_line_regex", result_line_regex)
    panel.assign_syntax(syntax)
    # Call create_output_panel a second time after assigning the above
    # settings, so that it'll be picked up as a result buffer
    # see: Packages/Default/exec.py#L228-L230
    panel = window.create_output_panel(name)
    # All our panels are read-only
    panel.set_read_only(True)
    return panel


def ensure_panel(window: sublime.Window, name: str, result_file_regex: str, result_line_regex: str,
                 syntax: str) -> 'Optional[sublime.View]':
    return window.find_output_panel(name) or create_panel(window, name, result_file_regex, result_line_regex, syntax)


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

    def run(self, edit: sublime.Edit, characters: 'Optional[str]' = "") -> None:
        with mutable(self.view):
            # Clear folds
            self.view.unfold(sublime.Region(0, self.view.size()))

            self.view.replace(edit, sublime.Region(0, self.view.size()), characters or "")

            # Clear the selection
            selection = self.view.sel()
            selection.clear()


class LspUpdateServerPanelCommand(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit, prefix: str, message: str) -> None:
        with mutable(self.view):
            self.view.insert(edit, self.view.size(), "{}: {}\n".format(prefix, message))
            total_lines, _ = self.view.rowcol(self.view.size())
            if total_lines <= SERVER_PANEL_MAX_LINES:
                return
            point = 0  # Starting from point 0 in the panel ...
            regions = []  # type: List[sublime.Region]
            for _ in range(0, total_lines - SERVER_PANEL_MAX_LINES):
                # ... collect all regions that span an entire line ...
                region = self.view.full_line(point)
                regions.append(region)
                point = region.b
            for region in reversed(regions):
                # ... and erase them in reverse order
                self.view.erase(edit, region)
