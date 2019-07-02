import sublime
import sublime_plugin

try:
    from typing import Optional
    assert Optional
except ImportError:
    pass


OUTPUT_PANEL_SETTINGS = {
    "auto_indent": False,
    "draw_indent_guides": False,
    "draw_white_space": "None",
    "gutter": True,
    'is_widget': True,
    "line_numbers": False,
    "margin": 3,
    "match_brackets": False,
    "scroll_past_end": False,
    "tab_size": 4,
    "translate_tabs_to_spaces": False,
    "word_wrap": False,
    "fold_buttons": True
}


def create_output_panel(window: sublime.Window, name: str) -> 'Optional[sublime.View]':
    panel = window.create_output_panel(name)
    settings = panel.settings()
    for key, value in OUTPUT_PANEL_SETTINGS.items():
        settings.set(key, value)
    return panel


def destroy_output_panels(window: sublime.Window) -> None:
    window.destroy_output_panel("references")
    window.destroy_output_panel("diagnostics")


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
    return panel


def ensure_panel(window: sublime.Window, name: str, result_file_regex: str, result_line_regex: str,
                 syntax: str) -> 'Optional[sublime.View]':
    return window.find_output_panel(name) or create_panel(window, name, result_file_regex, result_line_regex, syntax)


class LspClearPanelCommand(sublime_plugin.TextCommand):
    """
    A clear_panel command to clear the error panel.
    """

    def run(self, edit):
        self.view.set_read_only(False)
        self.view.erase(edit, sublime.Region(0, self.view.size()))
        self.view.set_read_only(True)


class LspUpdatePanelCommand(sublime_plugin.TextCommand):
    """
    A update_panel command to update the error panel with new text.
    """

    def run(self, edit, characters):
        entire_region = sublime.Region(0, self.view.size())
        # Clear folds
        self.view.unfold(entire_region)

        self.view.replace(edit, entire_region, characters)

        # Clear the selection
        selection = self.view.sel()
        selection.clear()
