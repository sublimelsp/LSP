from .core.edit import parse_text_edit
from .core.protocol import ColorPresentation
from .core.protocol import ColorPresentationParams
from .core.protocol import Request
from .core.registry import LspTextCommand
from .core.typing import List
from .core.views import range_to_region
import sublime


class LspColorPresentationCommand(LspTextCommand):

    capability = 'colorProvider'

    def run(self, edit: sublime.Edit, params: ColorPresentationParams) -> None:
        session = self.best_session(self.capability)
        if session:
            self._version = self.view.change_count()
            self._range = params['range']
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
        self._filtered_response = []  # type: List[ColorPresentation]
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
            self.view.run_command('lsp_apply_document_edit', {'changes': [parse_text_edit(text_edit, self._version)]})
