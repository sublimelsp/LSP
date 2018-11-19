from .settings import settings

import sublime
import sublime_plugin


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


def create_output_panel(window: sublime.Window, name: str) -> sublime.View:
    panel = window.create_output_panel(name)
    settings = panel.settings()
    for key, value in OUTPUT_PANEL_SETTINGS.items():
        settings.set(key, value)
    return panel


def destroy_output_panels(window: sublime.Window):
    window.destroy_output_panel("references")
    window.destroy_output_panel("diagnostics")


class LspClearPanelCommand(sublime_plugin.TextCommand):
    """
    A clear_panel command to clear the error panel.
    """

    def run(self, edit):
        self.view.set_read_only(False)
        self.view.erase(edit, sublime.Region(0, self.view.size()))
        self.view.set_read_only(True)


class LspUpdatePanelCommand(sublime_plugin.TextCommand):
    """ A update_panel command to update the error panel with new text """

    def run(self, edit, characters):
        view = self.view
        if settings.fold_diagnostics:
            # get the text of the first line of every folded region
            folded_regions = (view.substr(view.line(fr.a)) for fr in view.unfold(sublime.Region(0, view.size())))
            view.replace(edit, sublime.Region(0, view.size()), characters)

            for fr in folded_regions:
                # get all file lines
                for ln in view.find_by_selector("meta.diagnostic.preamble.lsp"):
                    if view.substr(ln) == fr:
                        # fold the region spanning from the end of the line of the
                        # filename to the to the end of the indented body
                        view.fold(sublime.Region(ln.b, view.indented_region(ln.b + 2).b - 1))
                        break

        else:
            view.replace(edit, sublime.Region(0, view.size()), characters)

        # Clear the selection
        view.sel().clear()
