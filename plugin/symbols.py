import weakref
from .core.protocol import Request, DocumentSymbol, SymbolInformation, SymbolKind, SymbolTag
from .core.registry import LspTextCommand
from .core.sessions import print_to_status_bar
from .core.typing import Any, List, Optional, Tuple, Dict, Generator, Union, cast
from .core.views import QuickPanelKind
from .core.views import range_to_region
from .core.views import SYMBOL_KIND_SCOPES
from .core.views import SYMBOL_KINDS
from .core.views import text_document_identifier
from contextlib import contextmanager
import os
import sublime
import sublime_plugin


SUPPRESS_INPUT_SETTING_KEY = 'lsp_suppress_input'


def unpack_lsp_kind(kind: SymbolKind) -> QuickPanelKind:
    return SYMBOL_KINDS.get(kind, sublime.KIND_AMBIGUOUS)


def format_symbol_kind(kind: SymbolKind) -> str:
    return SYMBOL_KINDS.get(kind, (None, None, str(kind)))[2]


def get_symbol_scope_from_lsp_kind(kind: SymbolKind) -> str:
    return SYMBOL_KIND_SCOPES.get(kind, "comment")


def symbol_information_to_quick_panel_item(
    item: SymbolInformation,
    show_file_name: bool = True
) -> sublime.QuickPanelItem:
    st_kind, st_icon, st_display_type = unpack_lsp_kind(item['kind'])
    tags = item.get("tags") or []
    if SymbolTag.Deprecated in tags:
        st_display_type = "⚠ {} - Deprecated".format(st_display_type)
    container = item.get("containerName") or ""
    details = []  # List[str]
    if container:
        details.append(container)
    if show_file_name:
        file_name = os.path.basename(item['location']['uri'])
        details.append(file_name)
    return sublime.QuickPanelItem(
            trigger=item["name"],
            details=details,
            annotation=st_display_type,
            kind=(st_kind, st_icon, st_display_type))


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

    def run(self, edit: sublime.Edit, event: Optional[Dict[str, Any]] = None) -> None:
        self.view.settings().set(SUPPRESS_INPUT_SETTING_KEY, True)
        session = self.best_session(self.capability)
        if session:
            params = {"textDocument": text_document_identifier(self.view)}
            session.send_request(
                Request("textDocument/documentSymbol", params, self.view, progress=True),
                lambda response: sublime.set_timeout(lambda: self.handle_response(response)),
                lambda error: sublime.set_timeout(lambda: self.handle_response_error(error)))

    def handle_response(self, response: Union[List[DocumentSymbol], List[SymbolInformation], None]) -> None:
        self.view.settings().erase(SUPPRESS_INPUT_SETTING_KEY)
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

    def handle_response_error(self, error: Any) -> None:
        self.view.settings().erase(SUPPRESS_INPUT_SETTING_KEY)
        print_to_status_bar(error)

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

    def process_symbols(
            self,
            items: Union[List[DocumentSymbol], List[SymbolInformation]]
    ) -> List[sublime.QuickPanelItem]:
        self.regions.clear()
        panel_items = []
        if 'selectionRange' in items[0]:
            items = cast(List[DocumentSymbol], items)
            panel_items = self.process_document_symbols(items)
        else:
            items = cast(List[SymbolInformation], items)
            panel_items = self.process_symbol_informations(items)
        # Sort both lists in sync according to the range's begin point.
        sorted_results = zip(*sorted(zip(self.regions, panel_items), key=lambda item: item[0][0].begin()))
        sorted_regions, sorted_panel_items = sorted_results
        self.regions = list(sorted_regions)  # type: ignore
        return list(sorted_panel_items)  # type: ignore

    def process_document_symbols(self, items: List[DocumentSymbol]) -> List[sublime.QuickPanelItem]:
        quick_panel_items = []  # type: List[sublime.QuickPanelItem]
        names = []  # type: List[str]
        for item in items:
            self.process_document_symbol_recursive(quick_panel_items, item, names)
        return quick_panel_items

    def process_document_symbol_recursive(self, quick_panel_items: List[sublime.QuickPanelItem], item: DocumentSymbol,
                                          names: List[str]) -> None:
        lsp_kind = item["kind"]
        self.regions.append((range_to_region(item['range'], self.view),
                             range_to_region(item['selectionRange'], self.view),
                             get_symbol_scope_from_lsp_kind(lsp_kind)))
        name = item['name']
        with _additional_name(names, name):
            st_kind, st_icon, st_display_type = unpack_lsp_kind(lsp_kind)
            formatted_names = " > ".join(names)
            st_details = item.get("detail") or ""
            if st_details:
                st_details = "{} | {}".format(st_details, formatted_names)
            else:
                st_details = formatted_names
            tags = item.get("tags") or []
            if SymbolTag.Deprecated in tags:
                st_display_type = "⚠ {} - Deprecated".format(st_display_type)
            quick_panel_items.append(
                sublime.QuickPanelItem(
                    trigger=name,
                    details=st_details,
                    annotation=st_display_type,
                    kind=(st_kind, st_icon, st_display_type)))
            children = item.get('children') or []  # type: List[DocumentSymbol]
            for child in children:
                self.process_document_symbol_recursive(quick_panel_items, child, names)

    def process_symbol_informations(self, items: List[SymbolInformation]) -> List[sublime.QuickPanelItem]:
        quick_panel_items = []  # type: List[sublime.QuickPanelItem]
        for item in items:
            self.regions.append((range_to_region(item['location']['range'], self.view),
                                 None, get_symbol_scope_from_lsp_kind(item['kind'])))
            quick_panel_item = symbol_information_to_quick_panel_item(item, show_file_name=False)
            quick_panel_items.append(quick_panel_item)
        return quick_panel_items


class SymbolQueryInput(sublime_plugin.TextInputHandler):
    def want_event(self) -> bool:
        return False

    def validate(self, txt: str) -> bool:
        return txt != ""

    def placeholder(self) -> str:
        return "Symbol"


class LspWorkspaceSymbolsCommand(LspTextCommand):

    capability = 'workspaceSymbolProvider'

    def input(self, _args: Any) -> sublime_plugin.TextInputHandler:
        return SymbolQueryInput()

    def run(self, edit: sublime.Edit, symbol_query_input: str) -> None:
        if symbol_query_input:
            session = self.best_session(self.capability)
            if session:
                params = {"query": symbol_query_input}
                request = Request("workspace/symbol", params, None, progress=True)
                self.weaksession = weakref.ref(session)
                session.send_request(request, lambda r: self._handle_response(
                    symbol_query_input, r), self._handle_error)

    def _open_file(self, symbols: List[SymbolInformation], index: int) -> None:
        if index != -1:
            session = self.weaksession()
            if session:
                session.open_location_async(symbols[index]['location'], sublime.ENCODED_POSITION)

    def _handle_response(self, query: str, response: Union[List[SymbolInformation], None]) -> None:
        if response:
            matches = response
            window = self.view.window()
            if window:
                window.show_quick_panel(
                    list(map(symbol_information_to_quick_panel_item, matches)),
                    lambda i: self._open_file(matches, i))
        else:
            sublime.message_dialog("No matches found for query string: '{}'".format(query))

    def _handle_error(self, error: Dict[str, Any]) -> None:
        reason = error.get("message", "none provided by server :(")
        msg = "command 'workspace/symbol' failed. Reason: {}".format(reason)
        sublime.error_message(msg)
