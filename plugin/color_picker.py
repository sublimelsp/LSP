from .core.views import lsp_color_to_hex
from .core.color_picker import ColorPickResult, color_picker
from .core.protocol import ColorInformation, TextEdit
from .core.typing import List
from .formatting import apply_text_edits_to_view
import sublime
import sublime_plugin


class LspChooseColorPicker(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit, color_information: ColorInformation, file_name: str) -> None:
        if not color_picker:
            sublime.status_message('Your platform does not support a ColorPicker yet.')
            return
        window = self.view.window()
        if not window:
            return

        def on_select(color: ColorPickResult) -> None:
            self.on_pick_color(color, color_information, file_name)

        color_picker.pick(on_select, color_information['color'])

    def on_pick_color(
        self, selected_color: ColorPickResult, color_information: ColorInformation, file_name: str
    ) -> None:
        if not selected_color:
            return
        window = self.view.window()
        if not window:
            return
        view = window.find_open_file(file_name)
        new_text = lsp_color_to_hex(selected_color)
        text_edits = [{
            "newText": new_text,
            "range": color_information['range']
        }]  # type: List[TextEdit]
        if view:
            apply_text_edits_to_view(text_edits, view)
