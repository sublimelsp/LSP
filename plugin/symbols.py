
from .core.protocol import SymbolKind
from .core.configurations import is_supported_view, LspTextCommand
from .core.clients import client_for_view
from .core.protocol import Request, Range
from .core.url import filename_to_uri


symbol_kind_names = {
    SymbolKind.File: "file",
    SymbolKind.Module: "module",
    SymbolKind.Namespace: "namespace",
    SymbolKind.Package: "package",
    SymbolKind.Class: "class",
    SymbolKind.Method: "method",
    SymbolKind.Function: "function",
    SymbolKind.Field: "field",
    SymbolKind.Variable: "variable",
    SymbolKind.Constant: "constant",
    SymbolKind.Interface: "interface",
    SymbolKind.Property: "property"
}


def format_symbol_kind(kind):
    return symbol_kind_names.get(kind, str(kind))


def format_symbol(item):
    """
    items may be a list of strings, or a list of string lists.
    In the latter case, each entry in the quick panel will show multiple rows
    """
    prefix = item.get("containerName", "")
    label = prefix + "." + item.get("name") if prefix else item.get("name")
    return [label, format_symbol_kind(item.get("kind"))]


class LspDocumentSymbolsCommand(LspTextCommand):
    def is_enabled(self):
        if is_supported_view(self.view):
            client = client_for_view(self.view)
            if client and client.has_capability('documentSymbolProvider'):
                return True
        return False

    def run(self, edit):
        client = client_for_view(self.view)
        if client:
            params = {
                "textDocument": {
                    "uri": filename_to_uri(self.view.file_name())
                }
            }
            request = Request.documentSymbols(params)
            client.send_request(request, self.handle_response)

    def handle_response(self, response):
        symbols = list(format_symbol(item) for item in response)
        self.symbols = response
        self.view.window().show_quick_panel(symbols, self.on_symbol_selected)

    def on_symbol_selected(self, symbol_index):
        selected_symbol = self.symbols[symbol_index]
        range = selected_symbol['location']['range']
        region = Range.from_lsp(range).to_region(self.view)
        self.view.show_at_center(region)
        self.view.sel().clear()
        self.view.sel().add(region)
