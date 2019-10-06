import sublime
from .core.logging import debug
from .core.protocol import Request, Range
from .core.protocol import SymbolKind
from .core.registry import LspTextCommand
from .core.url import filename_to_uri
from .core.views import range_to_region

try:
    from typing import List, Optional, Any, Tuple
    assert List and Optional and Any and Tuple
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


def format_symbol_kind(kind: int) -> str:
    return symbol_kind_names.get(kind, str(kind))


def format_symbol(item: dict) -> 'List[str]':
    """
    items may be a list of strings, or a list of string lists.
    In the latter case, each entry in the quick panel will show multiple rows
    """
    prefix = item.get("containerName", "")
    label = prefix + "." + item.get("name") if prefix else item.get("name")
    return [label, format_symbol_kind(item.get("kind") or 0)]


class LspDocumentSymbolsCommand(LspTextCommand):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)

    def is_enabled(self, event: 'Optional[dict]' = None) -> bool:
        return self.has_client_with_capability('documentSymbolProvider')

    def run(self, edit: sublime.Edit) -> None:
        client = self.client_with_capability('documentSymbolProvider')
        file_path = self.view.file_name()
        if client and file_path:
            params = {
                "textDocument": {
                    "uri": filename_to_uri(file_path)
                }
            }
            request = Request.documentSymbols(params)
            client.send_request(request, self.handle_response)

    def handle_response(self, response: 'Optional[List]') -> None:
        response_list = response or []
        symbols = list(format_symbol(item) for item in response_list)
        self.symbols = response_list
        window = self.view.window()
        if window:
            window.show_quick_panel(symbols, self.on_symbol_selected)

    def on_symbol_selected(self, symbol_index: int) -> None:
        if symbol_index == -1:
            return
        selected_symbol = self.symbols[symbol_index]
        range = selected_symbol.get('location', selected_symbol.get('range'))
        range = range.get('range', range)
        if not range:
            debug('could not recognize the type: expected either SymbolInformation or DocumentSymbol')
            return
        region = range_to_region(Range.from_lsp(range), self.view)
        self.view.show_at_center(region)
        self.view.sel().clear()
        self.view.sel().add(region)
