from __future__ import annotations

from .core.aio import show_quick_panel
from .core.edit import apply_text_edits
from .core.protocol import Error
from .core.protocol import Request
from .core.registry import LspTextCommand
from .core.views import range_to_region
from .core.views import text_document_identifier
from typing import TYPE_CHECKING
import sublime

if TYPE_CHECKING:
    from ..protocol import ColorInformation
    from ..protocol import ColorPresentation
    from ..protocol import ColorPresentationParams


class LspColorPresentationCommand(LspTextCommand):

    capability = 'colorProvider'

    async def run(self, color_information: ColorInformation) -> None:
        session = self.best_session(self.capability)
        if not session:
            return
        version = self.view.change_count()
        lsp_range = color_information['range']
        params: ColorPresentationParams = {
            'textDocument': text_document_identifier(self.view),
            'color': color_information['color'],
            'range': lsp_range
        }
        response = await session.request(Request.colorPresentation(params, self.view))
        if isinstance(response, Error) or not response:
            return
        window = self.view.window()
        if not window:
            return
        if version != self.view.change_count():
            return
        old_text = self.view.substr(range_to_region(lsp_range, self.view))
        filtered_response: list[ColorPresentation] = []
        for item in response:
            # Filter out items that would apply no change
            if text_edit := item.get('textEdit'):
                if text_edit['range'] == lsp_range and text_edit['newText'] == old_text:
                    continue
            elif item['label'] == old_text:
                continue
            filtered_response.append(item)
        if not filtered_response:
            return
        index = await show_quick_panel(
            window,
            [sublime.QuickPanelItem(item['label']) for item in filtered_response],
            placeholder="Change color format"
        )
        if index > -1:
            color_pres = filtered_response[index]
            text_edit = color_pres.get('textEdit') or {'range': lsp_range, 'newText': color_pres['label']}
            await apply_text_edits(self.view, [text_edit], label="Change Color Format", required_view_version=version)

    def want_event(self) -> bool:
        return False
