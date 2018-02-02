
from .core.protocol import Request, Range
from .core.url import filename_to_uri
from .core.clients import client_for_view
from .core.clients import LspTextCommand


class LspFormatDocumentCommand(LspTextCommand):
    def __init__(self, view):
        super(LspFormatDocumentCommand, self).__init__(view, 'documentFormattingProvider')

    def run(self, edit):
        client = client_for_view(self.view)
        if client:
            pos = self.view.sel()[0].begin()
            params = {
                "textDocument": {
                    "uri": filename_to_uri(self.view.file_name())
                },
                "options": {
                    "tabSize": self.view.settings().get("tab_size", 4),
                    "insertSpaces": True
                }
            }
            request = Request.formatting(params)
            client.send_request(
                request, lambda response: self.handle_response(response, pos))

    def handle_response(self, response, pos):
        self.view.run_command('lsp_apply_document_edit',
                              {'changes': response})


class LspFormatDocumentRangeCommand(LspTextCommand):
    def __init__(self, view):
        def last_check():
            if len(self.view.sel()) == 1:
                region = self.view.sel()[0]
                if region.begin() != region.end():
                    return True
            return False
        super(LspFormatDocumentRangeCommand, self).__init__(view, 'documentRangeFormattingProvider', last_check)

    def run(self, _):
        client = client_for_view(self.view)
        if client:
            region = self.view.sel()[0]
            params = {
                "textDocument": {
                    "uri": filename_to_uri(self.view.file_name())
                },
                "range": Range.from_region(self.view, region).to_lsp(),
                "options": {
                    "tabSize": self.view.settings().get("tab_size", 4),
                    "insertSpaces": True
                }
            }
            client.send_request(Request.rangeFormatting(params),
                                lambda response: self.view.run_command('lsp_apply_document_edit',
                                                                       {'changes': response}))
