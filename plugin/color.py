from .core.edit import apply_text_edits
from .core.protocol import ColorInformation
from .core.protocol import ColorPresentation
from .core.protocol import ColorPresentationParams
from .core.protocol import Request
from .core.registry import LspTextCommand
from .core.typing import List
from .core.views import range_to_region
from .core.views import text_document_identifier
import sublime


class LspColorPresentationCommand(LspTextCommand):

    capability = 'colorProvider'

    def run(self, edit: sublime.Edit, color_information: ColorInformation) -> None:
        session = self.best_session(self.capability)
        if session:
            self._version = self.view.change_count()
            self._range = color_information['range']
            params: ColorPresentationParams = {
                'textDocument': text_document_identifier(self.view),
                'color': color_information['color'],
                'range': self._range
            }
            session.send_request_async(Request.colorPresentation(params, self.view), self._handle_response_async)

    def want_event(self) -> bool:
        return False

    def _handle_response_async(self, response: List[ColorPresentation]) -> None:
        if not response:
            return
        window = self.view.window()
        if not window:
            return
        if self._version != self.view.change_count():
            return
        old_text = self.view.substr(range_to_region(self._range, self.view))
        self._filtered_response: List[ColorPresentation] = []
        for item in response:
            # Filter out items that would apply no change
            text_edit = item.get('textEdit')
            if text_edit:
                if text_edit['range'] == self._range and text_edit['newText'] == old_text:
                    continue
            elif item['label'] == old_text:
                continue
            self._filtered_response.append(item)
        if self._filtered_response:
            window.show_quick_panel(
                [sublime.QuickPanelItem(item['label']) for item in self._filtered_response],
                self._on_select,
                placeholder="Change color format")

    def _on_select(self, index: int) -> None:
        if index > -1:
            color_pres = self._filtered_response[index]
            text_edit = color_pres.get('textEdit') or {'range': self._range, 'newText': color_pres['label']}
            apply_text_edits(self.view, [text_edit], required_view_version=self._version)
