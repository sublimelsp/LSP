import weakref
from .core.protocol import DocumentSymbol
from .core.protocol import DocumentSymbolParams
from .core.protocol import Request
from .core.protocol import SymbolInformation
from .core.protocol import SymbolKind
from .core.protocol import SymbolTag
from .core.registry import LspTextCommand
from .core.sessions import print_to_status_bar
from .core.typing import Any, List, Optional, Tuple, Dict, Union, cast
from .core.views import range_to_region
# from .core.views import SUBLIME_KIND_ID_COLOR_SCOPES
from .core.views import SublimeKind
from .core.views import SYMBOL_KINDS
from .core.views import text_document_identifier
from .goto_diagnostic import PreselectedListInputHandler
import os
import sublime
import sublime_plugin


SUPPRESS_INPUT_SETTING_KEY = 'lsp_suppress_input'

SYMBOL_KIND_NAMES = {
    SymbolKind.File: "File",
    SymbolKind.Module: "Module",
    SymbolKind.Namespace: "Namespace",
    SymbolKind.Package: "Package",
    SymbolKind.Class: "Class",
    SymbolKind.Method: "Method",
    SymbolKind.Property: "Property",
    SymbolKind.Field: "Field",
    SymbolKind.Constructor: "Constructor",
    SymbolKind.Enum: "Enum",
    SymbolKind.Interface: "Interface",
    SymbolKind.Function: "Function",
    SymbolKind.Variable: "Variable",
    SymbolKind.Constant: "Constant",
    SymbolKind.String: "String",
    SymbolKind.Number: "Number",
    SymbolKind.Boolean: "Boolean",
    SymbolKind.Array: "Array",
    SymbolKind.Object: "Object",
    SymbolKind.Key: "Key",
    SymbolKind.Null: "Null",
    SymbolKind.EnumMember: "Enum Member",
    SymbolKind.Struct: "Struct",
    SymbolKind.Event: "Event",
    SymbolKind.Operator: "Operator",
    SymbolKind.TypeParameter: "Type Parameter"
}  # type: Dict[SymbolKind, str]


def unpack_lsp_kind(kind: SymbolKind) -> SublimeKind:
    return SYMBOL_KINDS.get(kind, sublime.KIND_AMBIGUOUS)


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


def symbol_to_list_input_item(
    view: sublime.View, item: Union[DocumentSymbol, SymbolInformation], hierarchy: str = ''
) -> sublime.ListInputItem:
    name = item['name']
    kind = item['kind']
    st_kind = SYMBOL_KINDS.get(kind, sublime.KIND_AMBIGUOUS)
    details = []
    selection_range = item.get('selectionRange')
    if selection_range:
        item = cast(DocumentSymbol, item)
        detail = item.get('detail')
        if detail:
            details.append(detail)
        if hierarchy:
            details.append(hierarchy + " > " + name)
        region = range_to_region(selection_range, view)
    else:
        item = cast(SymbolInformation, item)
        container_name = item.get('containerName')
        if container_name:
            details.append(container_name)
        region = range_to_region(item['location']['range'], view)
    if SymbolTag.Deprecated in (item.get('tags') or []) or item.get('deprecated', False):
        details.append("DEPRECATED")
    return sublime.ListInputItem(
        name,
        {'kind': kind, 'region': [region.a, region.b]},
        details=details,
        annotation=st_kind[2],
        kind=st_kind
    )


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
        self.items = []  # type: List[sublime.ListInputItem]
        self.kind = 0
        self.cached = False

    def run(
        self,
        edit: sublime.Edit,
        event: Optional[Dict[str, Any]] = None,
        kind: int = 0,
        index: Optional[int] = None
    ) -> None:
        pass

    def input(self, args: dict) -> Optional[sublime_plugin.CommandInputHandler]:
        if self.cached:
            self.cached = False
            window = self.view.window()
            if not window:
                return None
            symbol_kind = cast(SymbolKind, self.kind)
            initial_value = sublime.ListInputItem(
                SYMBOL_KIND_NAMES.get(symbol_kind, 'All Kinds'),
                self.kind,
                kind=SYMBOL_KINDS.get(symbol_kind, sublime.KIND_AMBIGUOUS))
            return DocumentSymbolsKindInputHandler(window, initial_value, self.view, self.items)
        self.kind = args.get('kind', 0)
        session = self.best_session(self.capability)
        if session:
            self.view.settings().set(SUPPRESS_INPUT_SETTING_KEY, True)
            params = {"textDocument": text_document_identifier(self.view)}  # type: DocumentSymbolParams
            session.send_request(
                Request.documentSymbols(params, self.view), self.handle_response_async, self.handle_response_error)
        return None

    def handle_response_async(self, response: Union[List[DocumentSymbol], List[SymbolInformation], None]) -> None:
        self.view.settings().erase(SUPPRESS_INPUT_SETTING_KEY)
        self.items.clear()
        if response and self.view.is_valid():
            if 'selectionRange' in response[0]:
                items = cast(List[DocumentSymbol], response)
                for item in items:
                    self.items.extend(self.process_document_symbol_recursive(item))
            else:
                items = cast(List[SymbolInformation], response)
                for item in items:
                    self.items.append(symbol_to_list_input_item(self.view, item))
            self.items.sort(key=lambda item: item.value['region'])
            window = self.view.window()
            if window:
                self.cached = True
                window.run_command('show_overlay', {'overlay': 'command_palette', 'command': 'lsp_document_symbols'})

    def handle_response_error(self, error: Any) -> None:
        self.view.settings().erase(SUPPRESS_INPUT_SETTING_KEY)
        print_to_status_bar(error)

    def process_document_symbol_recursive(
        self, item: DocumentSymbol, hierarchy: str = ''
    ) -> List[sublime.ListInputItem]:
        name = item['name']
        name_hierarchy = hierarchy + " > " + name if hierarchy else name
        items = [symbol_to_list_input_item(self.view, item, hierarchy)]
        for child in item.get('children') or []:
            items.extend(self.process_document_symbol_recursive(child, name_hierarchy))
        return items


class DocumentSymbolsKindInputHandler(PreselectedListInputHandler):

    def __init__(
        self,
        window: sublime.Window,
        initial_value: sublime.ListInputItem,
        view: sublime.View,
        items: List[sublime.ListInputItem],
    ) -> None:
        super().__init__(window, initial_value)
        self.view = view
        self.items = items
        self.old_selection = [sublime.Region(r.a, r.b) for r in view.sel()]
        self.last_selected = 0

    def name(self) -> str:
        return 'kind'

    def placeholder(self) -> str:
        return "Symbol Kind"

    def get_list_items(self) -> Tuple[List[sublime.ListInputItem], int]:
        items = [sublime.ListInputItem('All Kinds', 0, kind=sublime.KIND_AMBIGUOUS)]
        items.extend([
            sublime.ListInputItem(SYMBOL_KIND_NAMES[lsp_kind], lsp_kind, kind=st_kind)
            for lsp_kind, st_kind in SYMBOL_KINDS.items()
            if any(item.value['kind'] == lsp_kind for item in self.items)
        ])
        for index, item in enumerate(items):
            if item.value == self.last_selected:
                break
        else:
            index = 0
        return items, index

    def confirm(self, text: int) -> None:
        self.last_selected = text

    def next_input(self, args: dict) -> Optional[sublime_plugin.CommandInputHandler]:
        kind = args.get('kind')
        if kind is not None:
            return DocumentSymbolsInputHandler(self.view, kind, self.items, self.old_selection)


class DocumentSymbolsInputHandler(sublime_plugin.ListInputHandler):

    def __init__(
        self, view: sublime.View, kind: int, items: List[sublime.ListInputItem], old_selection: List[sublime.Region]
    ) -> None:
        super().__init__()
        self.view = view
        self.kind = kind
        self.items = items
        self.old_selection = old_selection

    def name(self) -> str:
        return 'index'

    def list_items(self) -> Tuple[List[sublime.ListInputItem], int]:
        items = [item for item in self.items if not self.kind or item.value['kind'] == self.kind]
        selected_index = 0
        if self.old_selection:
            pt = self.old_selection[0].b
            for index, item in enumerate(items):
                if item.value['region'][0] <= pt:
                    selected_index = index
                else:
                    break
        return items, selected_index

    def preview(self, text: dict) -> Union[str, sublime.Html]:
        r = text['region']
        self.view.run_command('lsp_selection_set', {'regions': [(r[0], r[1])]})
        self.view.show_at_center(r[0])
        return ""

    def cancel(self) -> None:
        if self.old_selection:
            self.view.run_command('lsp_selection_set', {'regions': [(r.a, r.b) for r in self.old_selection]})
            self.view.show_at_center(self.old_selection[0].begin())


class SymbolQueryInput(sublime_plugin.TextInputHandler):
    def want_event(self) -> bool:
        return False

    def placeholder(self) -> str:
        return "Enter symbol name"


class LspWorkspaceSymbolsCommand(LspTextCommand):

    capability = 'workspaceSymbolProvider'

    def input(self, _args: Any) -> sublime_plugin.TextInputHandler:
        return SymbolQueryInput()

    def run(self, edit: sublime.Edit, symbol_query_input: str, event: Optional[Any] = None) -> None:
        session = self.best_session(self.capability)
        if session:
            self.weaksession = weakref.ref(session)
            session.send_request(
                Request.workspaceSymbol({"query": symbol_query_input}),
                lambda r: self._handle_response(symbol_query_input, r),
                self._handle_error)

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
            sublime.message_dialog("No matches found for query: '{}'".format(query))

    def _handle_error(self, error: Dict[str, Any]) -> None:
        reason = error.get("message", "none provided by server :(")
        msg = "command 'workspace/symbol' failed. Reason: {}".format(reason)
        sublime.error_message(msg)
