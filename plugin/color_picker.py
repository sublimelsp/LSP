from .core.color_picker import ColorPickResult, ColorPicker
from .core.protocol import ColorInformation, TextEdit
from .core.typing import List
from .formatting import apply_text_edits_to_view
import sublime
import sublime_plugin


class LspChooseColorPicker(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit, color_information: ColorInformation, file_name: str) -> None:
        window = self.view.window()
        if not window:
            return
        view = window.find_open_file(file_name)
        if view:
            ColorPicker.pick(lambda selected_color: self.on_pick_color(view, selected_color, color_information), color_information)

    def on_pick_color(self, view: sublime.View, selected_color: ColorPickResult, color_information: ColorInformation) -> None:
        if not selected_color:
            return
        text_edits = [{
            "newText": selected_color,
            "range": color_information['range']
        }]  # type: List[TextEdit]
        apply_text_edits_to_view(text_edits, view)
