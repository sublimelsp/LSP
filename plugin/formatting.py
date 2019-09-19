import sublime
from .core.protocol import Request
from .core.edit import parse_text_edit
from .core.registry import LspTextCommand
from .core.url import filename_to_uri
from .core.views import region_to_range

try:
    from typing import Dict, Any, List, Optional
    assert Dict and Any and List and Optional
except ImportError:
    pass


def options_for_view(view: sublime.View) -> 'Dict[str, Any]':
    return {
        "tabSize": view.settings().get("tab_size", 4),
        "insertSpaces": True
    }


def apply_response_to_view(response: 'Optional[List[dict]]', view: sublime.View) -> None:
    edits = list(parse_text_edit(change) for change in response) if response else []
    view.run_command('lsp_apply_document_edit', {'changes': edits})


class LspFormatDocumentCommand(LspTextCommand):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)

    def is_enabled(self, event: 'Optional[dict]' = None) -> bool:
        return self.has_client_with_capability('documentFormattingProvider')

    def run(self, edit: 'Any') -> None:
        client = self.client_with_capability('documentFormattingProvider')
        if client:
            params = {
                "textDocument": {
                    "uri": filename_to_uri(self.view.file_name())
                },
                "options": options_for_view(self.view)
            }
            request = Request.formatting(params)
            client.send_request(
                request, lambda response: apply_response_to_view(response, self.view))


class LspFormatDocumentRangeCommand(LspTextCommand):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)

    def is_enabled(self, event: 'Optional[dict]' = None) -> bool:
        if self.has_client_with_capability('documentRangeFormattingProvider'):
            if len(self.view.sel()) == 1:
                region = self.view.sel()[0]
                if region.begin() != region.end():
                    return True
        return False

    def run(self, edit: sublime.Edit) -> None:
        client = self.client_with_capability('documentRangeFormattingProvider')
        if client:
            region = self.view.sel()[0]
            params = {
                "textDocument": {
                    "uri": filename_to_uri(self.view.file_name())
                },
                "range": region_to_range(self.view, region).to_lsp(),
                "options": options_for_view(self.view)
            }
            client.send_request(Request.rangeFormatting(params),
                                lambda response: apply_response_to_view(response, self.view))
