from .core.protocol import Request, Range
from .core.protocol import SymbolKind
from .core.registry import LspTextCommand
from .core.typing import Any, List, Optional, Tuple, Dict
from .core.views import location_to_encoded_filename
from .core.views import range_to_region
from .core.views import text_document_identifier
import os
import sublime
import sublime_plugin


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


class LspSelectionClearCommand(sublime_plugin.TextCommand):
    """
    Selections may not be modified outside the run method of a text command. Thus, to allow modification in an async
    context we need to have dedicated commands for this.

    https://github.com/sublimehq/sublime_text/issues/485#issuecomment-337480388
    """

    def run(self, _: sublime.Edit) -> None:
        self.view.sel().clear()


class LspSelectionAddCommand(sublime_plugin.TextCommand):

    def run(self, _: sublime.Edit, regions: List[Tuple[int, int]]) -> None:
        for region in regions:
            self.view.sel().add(sublime.Region(*region))


class LspDocumentSymbolsCommand(LspTextCommand):

    REGIONS_KEY = 'lsp_document_symbols'

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.old_regions = []  # type: List[sublime.Region]
        self.regions = []  # type: List[Tuple[sublime.Region, Optional[sublime.Region]]]
        self.found_at_least_one_nonempty_detail = False
        self.is_first_selection = False

    def is_enabled(self, event: Optional[dict] = None) -> bool:
        return self.has_client_with_capability('documentSymbolProvider')

    def run(self, edit: sublime.Edit) -> None:
        client = self.client_with_capability('documentSymbolProvider')
        if client:
            client.send_request(
                Request.documentSymbols({"textDocument": text_document_identifier(self.view)}), self.handle_response)

    def handle_response(self, response: Any) -> None:
        window = self.view.window()
        if window and isinstance(response, list) and len(response) > 0:
            self.old_regions = [sublime.Region(r.a, r.b) for r in self.view.sel()]
            self.is_first_selection = True
            window.show_quick_panel(
                self.process_symbols(response),
                self.on_symbol_selected,
                sublime.KEEP_OPEN_ON_FOCUS_LOST,
                0,
                self.on_highlighted)
            self.view.run_command("lsp_selection_clear")

    def region(self, index: int) -> sublime.Region:
        return self.regions[index][0]

    def selection_region(self, index: int) -> Optional[sublime.Region]:
        return self.regions[index][1]

    def on_symbol_selected(self, index: int) -> None:
        if index == -1:
            if len(self.old_regions) > 0:
                self.view.run_command("lsp_selection_add", {"regions": [(r.a, r.b) for r in self.old_regions]})
                self.view.show_at_center(self.old_regions[0].begin())
        else:
            region = self.selection_region(index) or self.region(index)
            self.view.run_command("lsp_selection_add", {"regions": [(region.a, region.a)]})
            self.view.show_at_center(region.a)
        self.view.erase_regions(self.REGIONS_KEY)
        self.old_regions.clear()
        self.regions.clear()

    def on_highlighted(self, index: int) -> None:
        if self.is_first_selection:
            self.is_first_selection = False
            return
        region = self.region(index)
        self.view.show_at_center(region.a)
        self.view.add_regions(self.REGIONS_KEY, [region], 'comment', '', sublime.DRAW_NO_FILL)

    def process_symbols(self, items: List[Dict[str, Any]]) -> List[List[str]]:
        self.regions.clear()
        if 'selectionRange' in items[0]:
            return self.process_document_symbols(items)
        else:
            return self.process_symbol_informations(items)

    def process_document_symbols(self, items: List[Dict[str, Any]]) -> List[List[str]]:
        quick_panel_items = []  # type: List[List[str]]
        self.found_at_least_one_nonempty_detail = False
        for item in items:
            self.process_document_symbol_recursive(quick_panel_items, item, 0)
        if self.found_at_least_one_nonempty_detail:
            return quick_panel_items
        else:
            return [[item[0], item[1]] for item in quick_panel_items]

    def process_document_symbol_recursive(self, quick_panel_items: List[List[str]], item: Dict[str, Any],
                                          depth: int) -> None:
        self.regions.append((range_to_region(Range.from_lsp(item['range']), self.view),
                             range_to_region(Range.from_lsp(item['selectionRange']), self.view)))
        name = ' ' * (4 * depth) + item['name']
        quick_panel_item = [name, format_symbol_kind(item['kind']), item.get('detail') or '']
        if quick_panel_item[2]:
            self.found_at_least_one_nonempty_detail = True
        quick_panel_items.append(quick_panel_item)
        children = item.get('children') or []
        for child in children:
            self.process_document_symbol_recursive(quick_panel_items, child, depth + 1)

    def process_symbol_informations(self, items: List[Dict[str, Any]]) -> List[List[str]]:
        quick_panel_items = []  # type: List[List[str]]
        for item in items:
            self.regions.append((range_to_region(Range.from_lsp(item['location']['range']), self.view), None))
            quick_panel_items.append([item['name'], format_symbol_kind(item['kind'])])
        return quick_panel_items


class SymbolQueryInput(sublime_plugin.TextInputHandler):

    def validate(self, txt: str) -> bool:
        return txt != ""

    def placeholder(self) -> str:
        return "Symbol"


class LspWorkspaceSymbolsCommand(LspTextCommand):
    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)

    def _format(self, s: Dict[str, Any]) -> str:
        file_name = os.path.basename(s['location']['uri'])
        symbol_kind = format_symbol_kind(s["kind"])
        name = "{} ({}) - {} -- {}".format(s['name'], symbol_kind, s.get('containerName', ""), file_name)
        return name

    def _open_file(self, symbols: List[Dict[str, Any]], index: int) -> None:
        if index != -1:
            symbol = symbols[index]
            window = self.view.window()
            if window:
                window.open_file(location_to_encoded_filename(symbol['location']), sublime.ENCODED_POSITION)

    def _handle_response(self, query: str, response: Optional[List[Dict[str, Any]]]) -> None:
        self.view.erase_status("lsp_workspace_symbols")
        if response:
            matches = response
            choices = list(map(lambda s: self._format(s), matches))
            window = self.view.window()
            if window:
                window.show_quick_panel(choices, lambda i: self._open_file(matches, i))
        else:
            sublime.message_dialog("No matches found for query string: '{}'".format(query))

    def _handle_error(self, error: Dict[str, Any]) -> None:
        self.view.erase_status("lsp_workspace_symbols")
        reason = error.get("message", "none provided by server :(")
        msg = "command 'workspace/symbol' failed. Reason: {}".format(reason)
        sublime.error_message(msg)

    def is_enabled(self) -> bool:
        return self.has_client_with_capability('workspaceSymbolProvider')

    def input(self, _args: Any) -> sublime_plugin.TextInputHandler:
        return SymbolQueryInput()

    def run(self, edit: sublime.Edit, symbol_query_input: str = "") -> None:
        if symbol_query_input:
            request = Request.workspaceSymbol({"query": symbol_query_input})
            client = self.client_with_capability('workspaceSymbolProvider')
            if client:
                self.view.set_status("lsp_workspace_symbols", "Searching for '{}'...".format(symbol_query_input))
                client.send_request(request, lambda r: self._handle_response(symbol_query_input, r), self._handle_error)
