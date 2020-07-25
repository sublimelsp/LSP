from .core.protocol import Request, Range
from .core.registry import LspTextCommand
from .core.typing import Any, List, Optional, Tuple, Dict, Generator
from .core.views import location_to_encoded_filename
from .core.views import range_to_region
from .core.views import SYMBOL_KINDS
from .core.views import text_document_identifier
from contextlib import contextmanager
import os
import sublime
import sublime_plugin


def format_symbol_kind(kind: int) -> str:
    if 1 <= kind <= len(SYMBOL_KINDS):
        return SYMBOL_KINDS[kind - 1][0]
    return str(kind)


def _kind_and_detail(item: Dict[str, Any]) -> str:
    kind = format_symbol_kind(item["kind"])
    detail = item.get("detail")
    if isinstance(detail, str) and detail:
        return "{} | {}".format(kind, detail)
    return kind


def format_symbol_scope(kind: int) -> str:
    if 1 <= kind <= len(SYMBOL_KINDS):
        return SYMBOL_KINDS[kind - 1][1]
    return 'comment'


@contextmanager
def _additional_name(names: List[str], name: str) -> Generator[None, None, None]:
    names.append(name)
    yield
    names.pop(-1)


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


class LspSelectionSetCommand(sublime_plugin.TextCommand):

    def run(self, _: sublime.Edit, regions: List[Tuple[int, int]]) -> None:
        self.view.sel().clear()
        for region in regions:
            self.view.sel().add(sublime.Region(*region))


class LspDocumentSymbolsCommand(LspTextCommand):

    capability = 'documentSymbolProvider'
    REGIONS_KEY = 'lsp_document_symbols'

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.old_regions = []  # type: List[sublime.Region]
        self.regions = []  # type: List[Tuple[sublime.Region, Optional[sublime.Region], str]]
        self.is_first_selection = False

    def run(self, edit: sublime.Edit) -> None:
        session = self.best_session(self.capability)
        if session:
            session.send_request(
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

    def scope(self, index: int) -> str:
        return self.regions[index][2]

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
        self.view.add_regions(self.REGIONS_KEY, [region], self.scope(index), '', sublime.DRAW_NO_FILL)

    def process_symbols(self, items: List[Dict[str, Any]]) -> List[List[str]]:
        self.regions.clear()
        if 'selectionRange' in items[0]:
            return self.process_document_symbols(items)
        else:
            return self.process_symbol_informations(items)

    def process_document_symbols(self, items: List[Dict[str, Any]]) -> List[List[str]]:
        quick_panel_items = []  # type: List[List[str]]
        names = []  # type: List[str]
        for item in items:
            self.process_document_symbol_recursive(quick_panel_items, item, names)
        return quick_panel_items

    def process_document_symbol_recursive(self, quick_panel_items: List[List[str]], item: Dict[str, Any],
                                          names: List[str]) -> None:
        kind = item['kind']
        self.regions.append((range_to_region(Range.from_lsp(item['range']), self.view),
                             range_to_region(Range.from_lsp(item['selectionRange']), self.view),
                             format_symbol_scope(kind)))
        name = item['name']
        with _additional_name(names, name):
            quick_panel_items.append([name, "{} | {}".format(_kind_and_detail(item), " > ".join(names))])
            children = item.get('children') or []
            for child in children:
                self.process_document_symbol_recursive(quick_panel_items, child, names)

    def process_symbol_informations(self, items: List[Dict[str, Any]]) -> List[List[str]]:
        quick_panel_items = []  # type: List[List[str]]
        for item in items:
            kind = item['kind']
            self.regions.append((range_to_region(Range.from_lsp(item['location']['range']), self.view),
                                 None, format_symbol_scope(kind)))
            container = item.get("containerName")
            second_row = _kind_and_detail(item)
            if container:
                second_row += " | {}".format(container)
            quick_panel_items.append([item['name'], second_row])
        return quick_panel_items


class SymbolQueryInput(sublime_plugin.TextInputHandler):

    def validate(self, txt: str) -> bool:
        return txt != ""

    def placeholder(self) -> str:
        return "Symbol"


class LspWorkspaceSymbolsCommand(LspTextCommand):

    capability = 'workspaceSymbolProvider'

    def input(self, _args: Any) -> sublime_plugin.TextInputHandler:
        return SymbolQueryInput()

    def run(self, edit: sublime.Edit, symbol_query_input: str = "") -> None:
        if symbol_query_input:
            session = self.best_session(self.capability)
            if session:
                self.view.set_status("lsp_workspace_symbols", "Searching for '{}'...".format(symbol_query_input))
                request = Request.workspaceSymbol({"query": symbol_query_input})
                session.send_request(request, lambda r: self._handle_response(
                    symbol_query_input, r), self._handle_error)

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
            window = self.view.window()
            if window:
                window.show_quick_panel(list(map(self._format, matches)), lambda i: self._open_file(matches, i))
        else:
            sublime.message_dialog("No matches found for query string: '{}'".format(query))

    def _handle_error(self, error: Dict[str, Any]) -> None:
        self.view.erase_status("lsp_workspace_symbols")
        reason = error.get("message", "none provided by server :(")
        msg = "command 'workspace/symbol' failed. Reason: {}".format(reason)
        sublime.error_message(msg)
