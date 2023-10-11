from .core.protocol import DocumentSymbol
from .core.protocol import DocumentSymbolParams
from .core.protocol import Request
from .core.protocol import SymbolInformation
from .core.protocol import SymbolKind
from .core.protocol import SymbolTag
from .core.protocol import WorkspaceSymbol
from .core.registry import LspTextCommand
from .core.registry import LspWindowCommand
from .core.sessions import print_to_status_bar
from .core.typing import Any, Callable, List, Optional, Tuple, Dict, TypeVar, Union, cast
from .core.views import range_to_region
from .core.views import SYMBOL_KINDS
from .core.views import text_document_identifier
from .goto_diagnostic import PreselectedListInputHandler
from abc import ABCMeta
from abc import abstractmethod
import functools
import os
import sublime
import sublime_plugin
import threading
import weakref


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
    deprecated = SymbolTag.Deprecated in (item.get('tags') or []) or item.get('deprecated', False)
    return sublime.ListInputItem(
        name,
        {'kind': kind, 'region': [region.a, region.b], 'deprecated': deprecated},
        details=" • ".join(details),
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

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.items = []  # type: List[sublime.ListInputItem]
        self.kind = 0
        self.cached = False
        self.has_matching_symbols = True

    def run(
        self,
        edit: sublime.Edit,
        event: Optional[Dict[str, Any]] = None,
        kind: int = 0,
        index: Optional[int] = None
    ) -> None:
        if index is None:
            if not self.has_matching_symbols:
                self.has_matching_symbols = True
                window = self.view.window()
                if window:
                    kind_name = SYMBOL_KIND_NAMES.get(cast(SymbolKind, self.kind))
                    window.status_message('No symbols of kind "{}" in this file'.format(kind_name))
                return
            self.kind = kind
            session = self.best_session(self.capability)
            if session:
                self.view.settings().set(SUPPRESS_INPUT_SETTING_KEY, True)
                params = {"textDocument": text_document_identifier(self.view)}  # type: DocumentSymbolParams
                session.send_request(
                    Request.documentSymbols(params, self.view), self.handle_response_async, self.handle_response_error)

    def input(self, args: dict) -> Optional[sublime_plugin.CommandInputHandler]:
        if self.cached:
            self.cached = False
            if self.kind and not any(item.value['kind'] == self.kind for item in self.items):
                self.has_matching_symbols = False
                return None
            window = self.view.window()
            if not window:
                return None
            symbol_kind = cast(SymbolKind, self.kind)
            initial_value = sublime.ListInputItem(
                SYMBOL_KIND_NAMES.get(symbol_kind, 'All Kinds'),
                self.kind,
                kind=SYMBOL_KINDS.get(symbol_kind, sublime.KIND_AMBIGUOUS))
            return DocumentSymbolsKindInputHandler(window, initial_value, self.view, self.items)
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
                window.run_command('show_overlay', {'overlay': 'command_palette', 'command': self.name()})

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

    def preview(self, text: Any) -> Union[str, sublime.Html, None]:
        if isinstance(text, dict):
            r = text.get('region')
            if r:
                self.view.run_command('lsp_selection_set', {'regions': [(r[0], r[1])]})
                self.view.show_at_center(r[0])
            if text.get('deprecated'):
                return "⚠ Deprecated"
        return ""

    def cancel(self) -> None:
        if self.old_selection:
            self.view.run_command('lsp_selection_set', {'regions': [(r.a, r.b) for r in self.old_selection]})
            self.view.show_at_center(self.old_selection[0].begin())


class LspWorkspaceSymbolsCommand(LspWindowCommand):

    capability = 'workspaceSymbolProvider'

    def __init__(self, window: sublime.Window) -> None:
        super().__init__(window)
        self.items = []  # type: List[sublime.ListInputItem]
        self.pending_request = False

    def run(
        self,
        symbol: Optional[Dict[str, Any]],
        text: str = ""
    ) -> None:
        if not symbol:
            return
        session = self.session()
        if session:
            session.open_location_async(symbol['location'], sublime.ENCODED_POSITION)

    def input(self, args: Dict[str, Any]) -> Optional[sublime_plugin.ListInputHandler]:
        # TODO maybe send an initial request with empty query string when the command is invoked?
        if 'symbol' not in args:
            return WorkspaceSymbolsInputHandler(self, args.get('text', ''))
        return None


def symbol_to_list_input_item2(item: Union[SymbolInformation, WorkspaceSymbol]) -> sublime.ListInputItem:
    # TODO merge this function with symbol_to_list_input_item
    name = item['name']
    kind = item['kind']
    location = item['location']
    st_kind = SYMBOL_KINDS.get(kind, sublime.KIND_AMBIGUOUS)
    details = []
    details.append(os.path.basename(location['uri']))
    container_name = item.get('containerName')
    if container_name:
        details.append(container_name)
    deprecated = SymbolTag.Deprecated in (item.get('tags') or []) or item.get('deprecated', False)
    return sublime.ListInputItem(
        name,
        {'kind': kind, 'location': location, 'deprecated': deprecated},
        details=" > ".join(details),
        annotation=st_kind[2],
        kind=st_kind
    )


class DynamicListInputHandler(sublime_plugin.ListInputHandler, metaclass=ABCMeta):
    """ A ListInputHandler which can update its items while typing in the input field.

    Derive from this class and override the `get_list_items` method for the initial list items, but don't implement
    `list_items`. Then you can call the `update` method with a list of `ListInputItem`s from within `on_modified`,
    which will be called after changes have been made to the input (with a small delay).

    To create an instance of the derived class, pass the command instance and the `text` command argument to the
    constructor, like this:

    def input(self, args):
        return MyDynamicListInputHandler(self, args.get('text', ''))

    For now, the type of the command must be a WindowCommand, but maybe it can be generalized later if needed.
    This class will set and modify an `_items` attribute of the command, so make sure that this attribute name is not
    used in another way in the command's class.
    """

    def __init__(self, command: sublime_plugin.WindowCommand, text: str) -> None:
        super().__init__()
        self.command = command
        self.text = text
        self.listener = None  # type: Optional[sublime_plugin.TextChangeListener]
        self.input_view = None  # type: Optional[sublime.View]

    def attach_listener(self) -> None:
        window = sublime.active_window()
        for buffer in sublime._buffers():  # type: ignore
            view = buffer.primary_view()
            # TODO what to do if there is another command palette open in the same window but in another group?
            if view.element() == 'command_palette:input' and view.window() == window:
                self.input_view = view
                break
        else:
            raise RuntimeError('Could not find the Command Palette input field view')
        self.listener = WorkspaceSymbolsQueryListener(self)
        self.listener.attach(buffer)
        # --- Hack needed because the initial_selection method is not supported on Python 3.3 API
        selection = self.input_view.sel()
        selection.clear()
        selection.add(len(self.text))
        # --- End of hack

    def list_items(self) -> List[sublime.ListInputItem]:
        if not self.text:  # Show initial items when the command was just invoked
            return self.get_list_items() or [sublime.ListInputItem("No Results", "")]
        else:  # Items were updated after typing
            items = getattr(self.command, '_items', None)
            if items:
                # Trick to select the topmost item; also see https://github.com/sublimehq/sublime_text/issues/6162
                sublime.set_timeout(self._select_first_item)
                return [sublime.ListInputItem("", "")] + items
            return [sublime.ListInputItem("No Results", "")]

    def _select_first_item(self) -> None:
        self.command.window.run_command('move', {'by': 'lines', 'forward': True})

    def initial_text(self) -> str:
        sublime.set_timeout(self.attach_listener)
        return self.text

    # Not supported on Python 3.3 API :-(
    def initial_selection(self) -> List[Tuple[int, int]]:
        pt = len(self.text)
        return [(pt, pt)]

    def validate(self, text: str) -> bool:
        return bool(text)

    def cancel(self) -> None:
        if self.listener and self.listener.is_attached():
            self.listener.detach()

    def confirm(self, text: str) -> None:
        if self.listener and self.listener.is_attached():
            self.listener.detach()

    def on_modified(self, text: str) -> None:
        """ Called after changes have been made to the input, with the text of the input field passed as argument. """
        pass

    @abstractmethod
    def get_list_items(self) -> List[sublime.ListInputItem]:
        """ The list items which are initially shown. """
        raise NotImplementedError()

    def update(self, items: List[sublime.ListInputItem]) -> None:
        """ Call this method to update the list items. """
        if not self.input_view:
            return
        setattr(self.command, '_items', items)
        text = self.input_view.substr(sublime.Region(0, self.input_view.size()))
        self.command.window.run_command('chain', {
            'commands': [
                # TODO is there a way to run the command again without having to close the overlay first, so that the
                # command palette won't change its width?
                ['hide_overlay', {}],
                [self.command.name(), {'text': text}]
            ]
        })
        # self.command.window.run_command(self.command.name(), {'text': self.text})


class WorkspaceSymbolsInputHandler(DynamicListInputHandler):

    def __init__(self, command: sublime_plugin.WindowCommand, text: str) -> None:
        super().__init__(command, text)

    def name(self) -> str:
        return 'symbol'

    def placeholder(self) -> str:
        return "Start typing to search"

    def preview(self, text: Any) -> Union[str, sublime.Html, None]:
        if isinstance(text, dict) and text.get('deprecated'):
            return "⚠ Deprecated"
        return ""

    def get_list_items(self) -> List[sublime.ListInputItem]:
        return []

    def on_modified(self, text: str) -> None:
        self.command = cast(LspWindowCommand, self.command)
        session = self.command.session()
        if session and self.input_view:
            change_count = self.input_view.change_count()
            session.send_request(
                Request.workspaceSymbol({"query": text}),
                functools.partial(self._handle_response_async, change_count),
                functools.partial(self._handle_response_error_async, change_count)
            )

    def _handle_response_async(self, change_count: int, response: Union[List[SymbolInformation], None]) -> None:
        if self.input_view and self.input_view.change_count() == change_count:
            self.update([symbol_to_list_input_item2(item) for item in response] if response else [])

    def _handle_response_error_async(self, change_count: int, error: Dict[str, Any]) -> None:
        if self.input_view and self.input_view.change_count() == change_count:
            self.update([])


T_Callable = TypeVar('T_Callable', bound=Callable[..., Any])


def debounced(user_function: T_Callable) -> T_Callable:
    """ Yet another debounce implementation :-) """
    DEBOUNCE_TIME = 0.5  # seconds
    @functools.wraps(user_function)
    def wrapped_function(*args: Any, **kwargs: Any) -> None:
        def call_function():
            if hasattr(wrapped_function, '_timer'):
                delattr(wrapped_function, '_timer')
            return user_function(*args, **kwargs)
        timer = getattr(wrapped_function, '_timer', None)
        if timer is not None:
            timer.cancel()
        timer = threading.Timer(DEBOUNCE_TIME, call_function)
        timer.start()
        setattr(wrapped_function, '_timer', timer)
    setattr(wrapped_function, '_timer', None)
    return cast(T_Callable, wrapped_function)


class WorkspaceSymbolsQueryListener(sublime_plugin.TextChangeListener):

    def __init__(self, handler: DynamicListInputHandler) -> None:
        super().__init__()
        self.weakhandler = weakref.ref(handler)

    @classmethod
    def is_applicable(cls, buffer: sublime.Buffer) -> bool:
        return False

    @debounced
    def on_text_changed(self, changes: List[sublime.TextChange]) -> None:
        handler = self.weakhandler()
        if not handler:
            return
        view = self.buffer.primary_view()
        if not view:
            return
        handler.on_modified(view.substr(sublime.Region(0, view.size())))
