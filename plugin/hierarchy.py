from .core.paths import simple_path
from .core.promise import Promise
from .core.protocol import CallHierarchyIncomingCall
from .core.protocol import CallHierarchyItem
from .core.protocol import CallHierarchyOutgoingCall
from .core.protocol import CallHierarchyPrepareParams
from .core.protocol import DocumentUri
from .core.protocol import Error
from .core.protocol import Range
from .core.protocol import Request
from .core.protocol import SymbolKind
from .core.protocol import TextDocumentPositionParams
from .core.protocol import TypeHierarchyItem
from .core.protocol import TypeHierarchyPrepareParams
from .core.registry import get_position
from .core.registry import LspTextCommand
from .core.registry import LspWindowCommand
from .core.registry import new_tree_view_sheet
from .core.sessions import Session
from .core.tree_view import TreeDataProvider
from .core.tree_view import TreeItem
from .core.typing import Callable, List, Optional, TypedDict, Union
from .core.typing import cast
from .core.views import make_command_link
from .core.views import SYMBOL_KINDS
from .core.views import text_document_position_params
from abc import ABCMeta
from abc import abstractmethod
from functools import partial
import sublime
import weakref


HierarchyItem = Union[CallHierarchyItem, TypeHierarchyItem]

HierarchyData = TypedDict('HierarchyData', {
    'detail': Optional[str],
    'kind': SymbolKind,
    'name': str,
    'range': Range,
    'selectionRange': Range,
    'uri': DocumentUri,
})


class HierarchyDataProvider(TreeDataProvider):

    def __init__(
        self,
        weaksession: 'weakref.ref[Session]',
        request: Callable[..., Request],
        request_handler: Callable[..., List[HierarchyData]],
        root_elements: List[HierarchyData]
    ) -> None:
        self.weaksession = weaksession
        self.request = request
        self.request_handler = request_handler
        self.root_elements = root_elements
        session = self.weaksession()
        self.session_name = session.config.name if session else None

    def get_children(self, element: Optional[HierarchyData]) -> Promise[List[HierarchyData]]:
        if element is None:
            return Promise.resolve(self.root_elements)
        session = self.weaksession()
        if not session:
            return Promise.resolve([])
        return session.send_request_task(self.request({'item': element})).then(self.request_handler)

    def get_tree_item(self, element: HierarchyData) -> TreeItem:
        command_url = sublime.command_url('lsp_open_location', {
            'location': {
                'targetUri': element['uri'],
                'targetRange': element['range'],
                'targetSelectionRange': element['selectionRange']
            },
            'session_name': self.session_name,
            'flags': sublime.ADD_TO_SELECTION | sublime.SEMI_TRANSIENT | sublime.CLEAR_TO_RIGHT
        })
        path = simple_path(self.weaksession(), element['uri'])
        return TreeItem(
            element['name'],
            kind=SYMBOL_KINDS.get(element['kind'], sublime.KIND_AMBIGUOUS),
            description=element['detail'] or '',
            tooltip="{}:{}".format(path, element['selectionRange']['start']['line'] + 1),
            command_url=command_url
        )


def make_data_provider(
    weaksession: 'weakref.ref[Session]', sheet_name: str, direction: int, response: List[HierarchyData]
) -> HierarchyDataProvider:
    if sheet_name == "Call Hierarchy":
        request = Request.incomingCalls if direction == 1 else Request.outgoingCalls
        handler = incoming_calls_handler if direction == 1 else outgoing_calls_handler
    elif sheet_name == "Type Hierarchy":
        request = Request.supertypes if direction == 1 else Request.subtypes
        handler = type_hierarchy_handler
    else:
        raise NotImplementedError('{} not implemented'.format(sheet_name))
    return HierarchyDataProvider(weaksession, request, handler, response)


def incoming_calls_handler(response: Union[List[CallHierarchyIncomingCall], None, Error]) -> List[HierarchyData]:
    return [
        to_hierarchy_item(call['from'], call['fromRanges'][0] if call['fromRanges'] else None) for call in response
    ] if isinstance(response, list) else []


def outgoing_calls_handler(response: Union[List[CallHierarchyOutgoingCall], None, Error]) -> List[HierarchyData]:
    return [to_hierarchy_item(call['to']) for call in response] if isinstance(response, list) else []


def type_hierarchy_handler(response: Union[List[TypeHierarchyItem], None, Error]) -> List[HierarchyData]:
    return [to_hierarchy_item(item) for item in response] if isinstance(response, list) else []


def to_hierarchy_item(
    item: Union[CallHierarchyItem, TypeHierarchyItem], selection_range: Optional[Range] = None
) -> HierarchyData:
    return {
        'detail': item.get('detail'),
        'name': item['name'],
        'kind': item['kind'],
        'range': item['range'],
        'selectionRange': selection_range or item['selectionRange'],
        'uri': item['uri'],
    }


def make_header(session_name: str, sheet_name: str, direction: int, root_elements: List[HierarchyItem]) -> str:
    if sheet_name == "Call Hierarchy":
        label = "Callers of…" if direction == 1 else "Calls from…"
        tooltip = "Show Outgoing Calls" if direction == 1 else "Show Incoming Calls"
    elif sheet_name == "Type Hierarchy":
        label = "Supertypes of…" if direction == 1 else "Subtypes of…"
        tooltip = "Show Subtypes" if direction == 1 else "Show Supertypes"
    else:
        raise NotImplementedError('{} not implemented'.format(sheet_name))
    new_direction = 2 if direction == 1 else 1
    return '{}: {} {}'.format(sheet_name, label, make_command_link('lsp_hierarchy_toggle', "⇄", {
            'session_name': session_name,
            'sheet_name': sheet_name,
            'direction': new_direction,
            'root_elements': root_elements
        }, tooltip=tooltip))


class LspHierarchyCommand(LspTextCommand, metaclass=ABCMeta):

    @classmethod
    @abstractmethod
    def request(
        cls, params: TextDocumentPositionParams, view: sublime.View
    ) -> Request[Union[List[HierarchyItem], Error, None]]:
        """ A function that generates the initial request when this command is invoked. """
        raise NotImplementedError()

    def is_visible(self, event: Optional[dict] = None, point: Optional[int] = None) -> bool:
        if self.applies_to_context_menu(event):
            return self.is_enabled(event, point)
        return True

    def run(self, edit: sublime.Edit, event: Optional[dict] = None, point: Optional[int] = None) -> None:
        self._window = self.view.window()
        session = self.best_session(self.capability)
        if not session:
            return
        position = get_position(self.view, event, point)
        if position is None:
            return
        params = text_document_position_params(self.view, position)
        session.send_request_async(
            self.request(params, self.view), partial(self._handle_response_async, weakref.ref(session)))

    def _handle_response_async(
        self,
        weaksession: 'weakref.ref[Session]',
        response: Union[List[CallHierarchyItem], List[TypeHierarchyItem], None]
    ) -> None:
        if not self._window or not self._window.is_valid():
            return
        if self.capability == 'callHierarchyProvider':
            sheet_name = "Call Hierarchy"
        elif self.capability == 'typeHierarchyProvider':
            sheet_name = "Type Hierarchy"
        else:
            raise NotImplementedError('{} not implemented'.format(self.capability))
        if not response:
            self._window.status_message("{} not available".format(sheet_name))
            return
        session = weaksession()
        if not session:
            return
        hierarchy_items = [to_hierarchy_item(item) for item in response]
        header = make_header(session.config.name, sheet_name, 1, hierarchy_items)
        data_provider = make_data_provider(weaksession, sheet_name, 1, hierarchy_items)
        new_tree_view_sheet(self._window, sheet_name, data_provider, header)
        open_first(self._window, session.config.name, hierarchy_items)


class LspHierarchyToggleCommand(LspWindowCommand):

    def run(
        self, session_name: str, sheet_name: str, direction: int, root_elements: List[HierarchyData]
    ) -> None:
        session = self.session_by_name(session_name)
        if not session:
            return
        header = make_header(session_name, sheet_name, direction, root_elements)
        data_provider = make_data_provider(weakref.ref(session), sheet_name, direction, root_elements)
        new_tree_view_sheet(self.window, sheet_name, data_provider, header)
        open_first(self.window, session.config.name, root_elements)


def open_first(window: sublime.Window, session_name: str, items: List[HierarchyData]) -> None:
    if items and window.is_valid():
        item = items[0]
        window.run_command('lsp_open_location', {
            'location': {
                'targetUri': item['uri'],
                'targetRange': item['range'],
                'targetSelectionRange': item['selectionRange']
            },
            'session_name': session_name,
            'flags': sublime.ADD_TO_SELECTION | sublime.SEMI_TRANSIENT | sublime.CLEAR_TO_RIGHT
        })


class LspCallHierarchyCommand(LspHierarchyCommand):

    capability = 'callHierarchyProvider'

    @classmethod
    def request(
        cls, params: TextDocumentPositionParams, view: sublime.View
    ) -> Request[Union[List[CallHierarchyItem], Error, None]]:
        return Request.prepareCallHierarchy(cast(CallHierarchyPrepareParams, params), view)


class LspTypeHierarchyCommand(LspHierarchyCommand):

    capability = 'typeHierarchyProvider'

    @classmethod
    def request(
        cls, params: TextDocumentPositionParams, view: sublime.View
    ) -> Request[Union[List[TypeHierarchyItem], Error, None]]:
        return Request.prepareTypeHierarchy(cast(TypeHierarchyPrepareParams, params), view)
