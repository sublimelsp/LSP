
from .core.protocol import SymbolKind
from .core.registry import client_for_view, LspTextCommand
from .core.protocol import Request, Range
from .core.url import filename_to_uri
from .core.views import range_to_region

try:
    from typing import List, Optional, Any
    assert List and Optional and Any
except ImportError:
    pass

symbol_kind_names = {
    SymbolKind.File: "file",
    SymbolKind.Module: "module",
    SymbolKind.Namespace: "namespace",
    SymbolKind.Package: "package",
    SymbolKind.Class: "class",
    SymbolKind.Method: "method",
    SymbolKind.Property: "property",
    SymbolKind.Field: "field",
    SymbolKind.Constructor: "constructor",
    SymbolKind.Enum: "enum",
    SymbolKind.Interface: "interface",
    SymbolKind.Function: "function",
    SymbolKind.Variable: "variable",
    SymbolKind.Constant: "constant",
    SymbolKind.String: "string",
    SymbolKind.Number: "number",
    SymbolKind.Boolean: "boolean",
    SymbolKind.Array: "array",
    SymbolKind.Object: "object",
    SymbolKind.Key: "key",
    SymbolKind.Null: "null",
    SymbolKind.EnumMember: "enum member",
    SymbolKind.Struct: "struct",
    SymbolKind.Event: "event",
    SymbolKind.Operator: "operator",
    SymbolKind.TypeParameter: "type parameter"
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
    def __init__(self, view):
        super().__init__(view)

    def is_enabled(self, event=None):
        return self.has_client_with_capability('documentSymbolProvider')

    def run(self, edit) -> None:
        client = client_for_view(self.view)
        if client:
            params = {
                "textDocument": {
                    "uri": filename_to_uri(self.view.file_name())
                }
            }
            request = Request.documentSymbols(params)
            client.send_request(request, self.handle_response)

    def handle_response(self, response: 'Optional[List]') -> None:
        response_list = response or []
        symbols = list(format_symbol(item) for item in response_list)
        self.symbols = response_list
        self.view.window().show_quick_panel(symbols, self.on_symbol_selected)

    def on_symbol_selected(self, symbol_index):
        selected_symbol = self.symbols[symbol_index]
        try:
            range = selected_symbol['location']['range']
        except KeyError:
            range = selected_symbol.get('range')
        if not range:
            debug('could not recognize the type: expected either SymbolInformation or DocumentSymbol')
            return
        region = range_to_region(Range.from_lsp(range), self.view)
        self.view.show_at_center(region)
        self.view.sel().clear()
        self.view.sel().add(region)
