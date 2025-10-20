from __future__ import annotations
from .core.constants import SYMBOL_KINDS
from .core.input_handlers import DynamicListInputHandler
from .core.input_handlers import PreselectedListInputHandler
from .core.promise import Promise
from .core.protocol import DocumentSymbol
from .core.protocol import DocumentSymbolParams
from .core.protocol import Location
from .core.protocol import Point
from .core.protocol import Range
from .core.protocol import Request
from .core.protocol import SymbolInformation
from .core.protocol import SymbolKind
from .core.protocol import SymbolTag
from .core.protocol import WorkspaceSymbol
from .core.registry import LspTextCommand
from .core.registry import LspWindowCommand
from .core.sessions import print_to_status_bar
from .core.views import offset_to_point
from .core.views import range_to_region
from .core.views import text_document_identifier
from typing import Any, List, TypedDict
from typing import cast
from typing_extensions import NotRequired, TypeGuard
import functools
import os
import sublime
import sublime_plugin


SUPPRESS_INPUT_SETTING_KEY = 'lsp_suppress_input'

SYMBOL_KIND_NAMES: dict[SymbolKind, str] = {
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
}


DocumentSymbolValue = TypedDict('DocumentSymbolValue', {
    'deprecated': bool,
    'kind': int,
    'range': Range
})

WorkspaceSymbolValue = TypedDict('WorkspaceSymbolValue', {
    'deprecated': bool,
    'kind': int,
    'location': NotRequired[Location],
    'session': str,
    'workspaceSymbol': NotRequired[WorkspaceSymbol]
})


def is_document_symbol_value(val: Any) -> TypeGuard[DocumentSymbolValue]:
    return isinstance(val, dict) and all(key in val for key in ('deprecated', 'kind', 'range'))


def symbol_to_list_input_item(
    item: DocumentSymbol | WorkspaceSymbol | SymbolInformation,
    hierarchy: str = '',
    session_name: str | None = None
) -> sublime.ListInputItem:
    name = item['name']
    kind = item['kind']
    st_kind = SYMBOL_KINDS.get(kind, sublime.KIND_AMBIGUOUS)
    details: list[str] = []
    deprecated = SymbolTag.Deprecated in (item.get('tags') or []) or item.get('deprecated', False)
    value = {'kind': kind, 'deprecated': deprecated}
    details_separator = " • "
    selection_range = item.get('selectionRange')
    if selection_range:  # Response from textDocument/documentSymbol request
        item = cast(DocumentSymbol, item)
        detail = item.get('detail')
        if detail:
            details.append(detail)
        if hierarchy:
            details.append(hierarchy + " > " + name)
        value['range'] = selection_range
    elif session_name is None:  # Response from textDocument/documentSymbol request
        item = cast(SymbolInformation, item)
        container_name = item.get('containerName')
        if container_name:
            details.append(container_name)
        value['range'] = item['location']['range']
    else:  # Response from workspace/symbol request
        item = cast(WorkspaceSymbol, item)  # Either WorkspaceSymbol or SymbolInformation, but possibly undecidable
        details_separator = " > "
        location = item['location']
        details.append(os.path.basename(location['uri']))
        container_name = item.get('containerName')
        if container_name:
            details.append(container_name)
        if 'range' in location:
            value['location'] = location
        else:
            value['workspaceSymbol'] = item
        value['session'] = session_name
    return sublime.ListInputItem(
        name,
        value,
        details=details_separator.join(details),
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

    def run(self, _: sublime.Edit, regions: list[tuple[int, int]]) -> None:
        for region in regions:
            self.view.sel().add(sublime.Region(*region))


class LspSelectionSetCommand(sublime_plugin.TextCommand):

    def run(self, _: sublime.Edit, regions: list[tuple[int, int]]) -> None:
        self.view.sel().clear()
        for region in regions:
            self.view.sel().add(sublime.Region(*region))


class LspDocumentSymbolsCommand(LspTextCommand):

    capability = 'documentSymbolProvider'

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.items: list[sublime.ListInputItem] = []
        self.kind = 0
        self.cached = False
        self.has_matching_symbols = True

    def run(
        self,
        edit: sublime.Edit,
        event: dict[str, Any] | None = None,
        kind: int = 0,
        index: int | None = None
    ) -> None:
        if index is None:
            if not self.has_matching_symbols:
                self.has_matching_symbols = True
                window = self.view.window()
                if window:
                    kind_name = SYMBOL_KIND_NAMES.get(cast(SymbolKind, self.kind))
                    window.status_message(f'No symbols of kind "{kind_name}" in this file')
                return
            self.kind = kind
            session = self.best_session(self.capability)
            if session:
                self.view.settings().set(SUPPRESS_INPUT_SETTING_KEY, True)
                params: DocumentSymbolParams = {"textDocument": text_document_identifier(self.view)}
                session.send_request(
                    Request.documentSymbols(params, self.view), self.handle_response_async, self.handle_response_error)

    def input(self, args: dict) -> sublime_plugin.CommandInputHandler | None:
        if self.cached:
            self.cached = False
            if self.kind and not any(item.value['kind'] == self.kind for item in self.items):
                self.has_matching_symbols = False
                self._reset_suppress_input()
                return None
            window = self.view.window()
            if not window:
                return None
            symbol_kind = cast(SymbolKind, self.kind)
            initial_value = sublime.ListInputItem(
                SYMBOL_KIND_NAMES.get(symbol_kind, 'All Kinds'),
                self.kind,
                kind=SYMBOL_KINDS.get(symbol_kind, sublime.KIND_AMBIGUOUS))
            sublime.set_timeout(self._reset_suppress_input)
            return DocumentSymbolsKindInputHandler(window, initial_value, self.view, self.items)
        return None

    def handle_response_async(self, response: list[DocumentSymbol] | list[SymbolInformation] | None) -> None:
        self.items.clear()
        if response and self.view.is_valid():
            if 'selectionRange' in response[0]:
                items = cast(List[DocumentSymbol], response)
                for item in items:
                    self.items.extend(self.process_document_symbol_recursive(item))
            else:
                items = cast(List[SymbolInformation], response)
                for item in items:
                    self.items.append(symbol_to_list_input_item(item))
            self.items.sort(key=lambda item: Point.from_lsp(item.value['range']['start']))
            window = self.view.window()
            if window:
                self.cached = True
                window.run_command('show_overlay', {'overlay': 'command_palette', 'command': self.name()})

    def handle_response_error(self, error: Any) -> None:
        self._reset_suppress_input()
        print_to_status_bar(error)

    def _reset_suppress_input(self) -> None:
        self.view.settings().erase(SUPPRESS_INPUT_SETTING_KEY)

    def process_document_symbol_recursive(
        self, item: DocumentSymbol, hierarchy: str = ''
    ) -> list[sublime.ListInputItem]:
        name = item['name']
        name_hierarchy = hierarchy + " > " + name if hierarchy else name
        items = [symbol_to_list_input_item(item, hierarchy)]
        for child in item.get('children') or []:
            items.extend(self.process_document_symbol_recursive(child, name_hierarchy))
        return items


class DocumentSymbolsKindInputHandler(PreselectedListInputHandler):

    def __init__(
        self,
        window: sublime.Window,
        initial_value: sublime.ListInputItem,
        view: sublime.View,
        items: list[sublime.ListInputItem],
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

    def get_list_items(self) -> tuple[list[sublime.ListInputItem], int]:
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

    def next_input(self, args: dict) -> sublime_plugin.CommandInputHandler | None:
        kind = args.get('kind')
        if kind is not None:
            return DocumentSymbolsInputHandler(self.view, kind, self.items, self.old_selection)


class DocumentSymbolsInputHandler(sublime_plugin.ListInputHandler):

    def __init__(
        self, view: sublime.View, kind: int, items: list[sublime.ListInputItem], old_selection: list[sublime.Region]
    ) -> None:
        super().__init__()
        self.view = view
        self.kind = kind
        self.items = items
        self.old_selection = old_selection

    def name(self) -> str:
        return 'index'

    def list_items(self) -> tuple[list[sublime.ListInputItem], int]:
        items = [item for item in self.items if not self.kind or item.value['kind'] == self.kind]
        selected_index = 0
        if self.old_selection:
            caret_point = offset_to_point(self.view, self.old_selection[0].b)
            for index, item in enumerate(items):
                start = item.value['range']['start']
                if start['line'] < caret_point.row or \
                        start['line'] == caret_point.row and start['character'] <= caret_point.col:
                    selected_index = index
                else:
                    break
        return items, selected_index

    def preview(self, text: DocumentSymbolValue | None) -> str | sublime.Html | None:
        if is_document_symbol_value(text):
            region = range_to_region(text['range'], self.view)
            self.view.run_command('lsp_selection_set', {'regions': [(region.a, region.b)]})
            self.view.show_at_center(region.a)
            if text['deprecated']:
                return "⚠ Deprecated"
        return ""

    def cancel(self) -> None:
        if self.old_selection:
            self.view.run_command('lsp_selection_set', {'regions': [(r.a, r.b) for r in self.old_selection]})
            self.view.show_at_center(self.old_selection[0].begin())


class LspWorkspaceSymbolsCommand(LspWindowCommand):

    capability = 'workspaceSymbolProvider'

    def run(self, symbol: WorkspaceSymbolValue) -> None:
        session_name = symbol['session']
        session = self.session_by_name(session_name)
        if session:
            location = symbol.get('location')
            if location:
                session.open_location_async(location, sublime.NewFileFlags.ENCODED_POSITION)
            else:
                session.send_request(
                    Request.resolveWorkspaceSymbol(symbol['workspaceSymbol']),  # type: ignore
                    functools.partial(self._on_resolved_symbol_async, session_name))

    def input(self, args: dict[str, Any]) -> sublime_plugin.ListInputHandler | None:
        if 'symbol' not in args:
            return WorkspaceSymbolsInputHandler(self, args)
        return None

    def _on_resolved_symbol_async(self, session_name: str, response: WorkspaceSymbol) -> None:
        location = cast(Location, response['location'])
        session = self.session_by_name(session_name)
        if session:
            session.open_location_async(location, sublime.NewFileFlags.ENCODED_POSITION)


class WorkspaceSymbolsInputHandler(DynamicListInputHandler):

    def name(self) -> str:
        return 'symbol'

    def placeholder(self) -> str:
        return "Start typing to search"

    def preview(self, text: WorkspaceSymbolValue | None) -> str | sublime.Html | None:
        if isinstance(text, dict) and text.get('deprecated'):
            return "⚠ Deprecated"
        return ""

    def on_modified(self, text: str) -> None:
        if not self.input_view:
            return
        change_count = self.input_view.change_count()
        self.command = cast(LspWindowCommand, self.command)
        promises: list[Promise[list[sublime.ListInputItem]]] = []
        for session in self.command.sessions():
            promises.append(
                session.send_request_task(Request.workspaceSymbol({"query": text}))
                    .then(functools.partial(self._handle_response_async, session.config.name)))
        Promise.all(promises).then(functools.partial(self._on_all_responses, change_count))

    def _handle_response_async(
        self, session_name: str, response: list[SymbolInformation] | list[WorkspaceSymbol] | None
    ) -> list[sublime.ListInputItem]:
        return [symbol_to_list_input_item(item, session_name=session_name) for item in response] if response else []

    def _on_all_responses(self, change_count: int, item_lists: list[list[sublime.ListInputItem]]) -> None:
        if self.input_view and self.input_view.change_count() == change_count:
            items: list[sublime.ListInputItem] = []
            for item_list in item_lists:
                items.extend(item_list)
            self.update(items)
