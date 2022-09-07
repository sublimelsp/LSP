from ColorPicker.sublimecp import sublime_plugin
from .core.color_picker import ColorPickResult, ColorPicker
import sublime
from .core.protocol import ColorInformation, TextEdit
from .core.typing import List
from .formatting import apply_text_edits_to_view


class LspChooseColorPicker(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit, color_information: ColorInformation) -> None:
        print('color_information', color_information)
        if not ColorPicker.is_enabled():
            sublime.status_message('Install "ColorPicker" from PackageControl in order to pick colors. (restart required)')
            return
        window = self.view.window()
        if not window:
            return
        ColorPicker.pick(window, lambda selected_color: self.on_pick_color(selected_color, color_information))

    def on_pick_color(self, selected_color: ColorPickResult, color_information: ColorInformation) -> None:
        if not selected_color:
            return
        text_edits = [{
            "newText": selected_color,
            "range": color_information['range']
        }]  # type: List[TextEdit]
        apply_text_edits_to_view(text_edits, self.view)
